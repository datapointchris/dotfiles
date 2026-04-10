# Claude Code - Dotfiles Development Context

## Critical Rules

**Note**: The following universal rules are defined in `~/.claude/CLAUDE.md` and apply to ALL projects:

- System Environment (GNU tools)
- Git Safety Protocol, Git Commit Messages, Git Hygiene
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

**App Installation Patterns** (⚠️ CRITICAL - Three distinct patterns):

1. **Go Apps** (sess, toolbox): Installed via `go install` from packages.yml
   - Defined in `packages.yml` under `go_tools` with `package` field (go install path)
   - Installer: `management/common/install/language-tools/go-tools.sh`
   - Development in `~/tools/{app}/`, push to GitHub, `go install` gets latest
   - Binary location: `~/go/bin/`

2. **Shell Script Apps** (menu, notes): Symlinked from repo
   - Located in `apps/{platform}/` as executable files
   - Symlinked by `link_apps()` → `~/.local/bin/`
   - Note: `link_apps()` skips directories, only symlinks files

3. **Personal CLI Tools** (theme, font): Git clone + symlink
   - Custom installers in `management/common/install/custom-installers/`
   - Clone to `~/.local/share/{tool}/`, symlink bin → `~/.local/bin/`
   - Development in `~/tools/{app}/`, push to GitHub, run `{tool} upgrade`

See `docs/learnings/app-installation-patterns.md` for full details.

**Standards First**: Always prefer industry-standard defaults (e.g., GoReleaser naming, conventional commits). Do not deviate unless there is a documented reason.

**Critical Bash Gotcha - Arithmetic with set -e** (⚠️ This has caught us 4+ times):

- `((COUNTER++))` returns 0 (false) when COUNTER is 0, causing `set -e` to exit the script
- **Always use:** `COUNTER=$((COUNTER + 1))` instead of `((COUNTER++))`
- **Or use:** `((COUNTER++)) || true` to prevent exit
- This affects any arithmetic expression that evaluates to 0: `((VAR--))`, `((VAR *= 0))`, etc.

**Shell Libraries** (`~/.local/shell/`) — see `docs/architecture/shell-libraries.md`:

| Scenario | Library | Functions |
|----------|---------|-----------|
| Logged/monitored scripts | logging.sh | `log_info/success/warning/error/fatal` |
| Visual/interactive scripts | formatting.sh | `print_success/error/warning/info` |
| Visual structure | formatting.sh | `print_header/section/banner/title` |
| Cleanup/error traps | error-handling.sh | `enable_error_traps`, `register_cleanup` |

**GitHub Release Installers** (⚠️ Use library for new installers):

- Use `management/common/lib/github-release-installer.sh` for new GitHub release installers
- See `management/common/install/github-releases/` for all current scripts
- See `docs/architecture/github-release-installer.md`

**Zsh Configuration Setup** (⚠️ This is the CORRECT setup - do not second-guess it):

- `ZDOTDIR` is defined in `/etc/zshenv` (system-wide) pointing to `~/.config/zsh`
- There is NO `.zprofile` or `.zshenv` in the home directory (and there should NOT be)
- `.zshrc` is located in `~/.config/zsh/.zshrc` (symlinked from dotfiles repo)
- This XDG-compliant setup is intentional and correct
- Standalone shell scripts in `apps/` must source logging.sh library if they need logging (they run in their own bash process, not in the shell environment)

**Installation Script Testing**:

- `install.sh` requires `--machine NAME` and sudo — Claude Code cannot provide interactive sudo
- Test individual phase scripts directly, or use Docker containers with passwordless sudo
- Do NOT run `./install.sh` directly in Claude Code sessions

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

A cross-platform dotfiles repository with manifest-driven installation and shared configurations with platform-specific overrides for macOS, Ubuntu, WSL Ubuntu, and Arch Linux. The repository emphasizes automation, documentation, and ergonomic developer workflows.

**Directory Structure**:

- `configs/` - Platform configurations (what gets deployed)
  - `common/` - Shared configurations (Neovim, tmux, zsh, git)
  - `macos/` - macOS-specific dotfiles and GUI app configs
  - `wsl/` - Ubuntu WSL configurations for restricted work environment
  - `arch/` - Arch Linux configurations
  - `ubuntu/` - Ubuntu server configurations
- `apps/` - Personal CLI applications (shell scripts only, see `apps/` for full listing)
  - `common/` - Cross-platform tools (menu, notes, backmeup, safekeep, patterns, and more)
  - `macos/` - macOS-specific tools
  - `arch/` - Arch Linux-specific tools (rofi menus, screen control)
- `management/` - Repository management tools
  - `machines/` - Machine manifests (YAML defining what to install per computer)
  - `shell/` - Modular shell aliases and functions (build source)
  - `symlinks/` - Symlinks manager (Python)
  - `orchestration/` - Platform detection and installer runner
  - `offline/` - Offline installation support (connectivity testing, bundles)
  - `{platform}/` - Platform-specific install scripts
  - `packages.yml` - Package definitions
- `docs/` - MkDocs-based documentation site
- `.claude/` - Skills and hooks for Claude Code integration
- `.planning/` - **NOT TRACKED BY GIT** - Ephemeral planning guides and status tracking

**Key Systems**:

- **Machine Manifests** - YAML files in `management/machines/` defining what to install per computer type
- **Shell Build** - `shell/build-shell.sh` concatenates modular shell files based on manifest groups
- **Symlink Manager** - Deploys dotfiles from repo to home directory via `task symlinks:link`
- **Theme System** (`theme`) - Unified theme management across ghostty, tmux, btop, and Neovim
- **Tools Discovery** (`toolbox`) - CLI for exploring installed development tools
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
├── {topic.md}           # High-level topics that don't need a subdirectory
├── apps/                # Personal CLI application docs
├── architecture/        # HOW and WHY everything works
├── claude-code/         # Claude Code integration, agents, hooks
├── configuration/       # Customization guides
├── development/         # Testing and contributing
├── reference/           # Quick lookup (platforms, tools, tasks)
├── research/            # Technical research and exploration
└── learnings/           # Extracted wisdom from bugs and discoveries
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

- **Symlinks Manager** — `task symlinks:{link,check,show}`
- **Theme** (`theme`) — unified theming across ghostty, tmux, btop, Neovim
- **Toolbox** (`toolbox`) — CLI for discovering installed dev tools, registry at `configs/common/.config/toolbox/registry.yml`
- **Task** — `task --list-all` for available tasks; complex logic lives in `management/` scripts

## Learnings Directory

Document critical lessons in `docs/learnings/descriptive-name.md` (30-50 lines max). Add to `mkdocs.yml` navigation. Format: Problem → Solution → Key Learnings (actionable bullets).

- todo.md is for creating future work items, not to be used for planning, moved to .planning, or changed in any way
