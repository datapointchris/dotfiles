# Complete Tool Inventory

**Last Updated**: 2025-11-03
**Total Tools**: 100+

This document organizes all installed tools by category and installation method. For detailed usage information on the most useful tools, see `docs/tools/registry.yml` or use the `tools` command.

---

## Package Management Philosophy

**System Tools** → brew/apt/pacman
**Python** → uv
**Node.js** → nvm

See `CLAUDE.md` for detailed philosophy.

---

## Table of Contents

- [File Management & Viewing](#file-management--viewing)
- [Search & Text Processing](#search--text-processing)
- [Navigation](#navigation)
- [Version Control](#version-control)
- [Editors & IDEs](#editors--ides)
- [Terminal & Multiplexing](#terminal--multiplexing)
- [Language Version Managers](#language-version-managers)
- [Programming Languages](#programming-languages)
- [Language Servers (LSP)](#language-servers-lsp)
- [Linters & Formatters](#linters--formatters)
- [Containerization & Infrastructure](#containerization--infrastructure)
- [Cloud & DevOps](#cloud--devops)
- [Database Tools](#database-tools)
- [Build & Task Automation](#build--task-automation)
- [System Utilities](#system-utilities)
- [Network](#network)
- [Media & Graphics](#media--graphics)
- [macOS-Specific](#macos-specific)
- [Fun & Demo](#fun--demo)

---

## File Management & Viewing

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **bat** | brew | Syntax-highlighting cat with git integration | ✅ |
| **eza** | brew | Modern ls replacement with icons | ✅ |
| **fd** | brew | Fast find alternative | ✅ |
| **tree** | brew | Directory tree visualization | |
| **yazi** | brew | Terminal file manager with image preview | ✅ |
| **duf** | brew | Modern df alternative (disk usage) | |
| **duti** | brew | File association manager (macOS) | |

**Commands to explore**:

```bash
tools show bat        # Learn about bat
tools show eza        # Learn about eza
tools show yazi       # Learn about yazi
```

---

## Search & Text Processing

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **ripgrep** (rg) | brew | Ultra-fast recursive grep | ✅ |
| **fzf** | brew | Fuzzy finder for files/history | ✅ |
| **grep** | brew | GNU grep | |
| **gnu-sed** | brew | GNU sed (available as `gsed`) | |
| **jq** | brew | JSON processor | ✅ |
| **glow** | brew | Markdown renderer for terminal | |

---

## Navigation

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **zoxide** | brew | Smarter cd that learns habits | ✅ |

---

## Version Control

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **git** | brew | Distributed version control | ✅ |
| **gh** | brew | GitHub CLI | ✅ |
| **lazygit** | brew | Terminal UI for git | ✅ |
| **git-delta** | brew | Syntax-highlighting git diff viewer | ✅ |
| **git-secrets** | brew | Prevents committing secrets | |

---

## Editors & IDEs

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **neovim** | brew | Modern vim-based editor | ✅ |

---

## Terminal & Multiplexing

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **tmux** | brew | Terminal multiplexer | ✅ |
| **tmuxinator** | brew | Tmux session manager | |
| **zsh-syntax-highlighting** | brew | ZSH syntax highlighting | |
| **terminal-notifier** | brew | macOS notification from terminal | |

---

## Language Version Managers

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **uv** | cargo | Fast Python package/version manager | ✅ |
| **nvm** | script | Node.js version manager | ✅ |

**Active versions**:

```bash
node --version    # v24.11.0 (via nvm)
python --version  # (via uv)
```

---

## Programming Languages

| Tool | Install | Description |
|------|---------|-------------|
| **go** | brew | Go programming language |
| **ruby** | brew | Ruby programming language |
| **lua** | brew | Lua scripting language |
| **luajit** | brew | LuaJIT compiler |
| **luarocks** | brew | Lua package manager |
| **sbt** | brew | Scala build tool |
| **openjdk** | brew | OpenJDK Java |
| **sbcl** | brew | Steel Bank Common Lisp |

**Note**: Python and Node.js managed via uv/nvm respectively.

---

## Language Servers (LSP)

All installed via **npm** (nvm-managed):

| Tool | Languages | In Registry |
|------|-----------|-------------|
| **typescript-language-server** | TypeScript, JavaScript | ✅ |
| **bash-language-server** | Bash, Shell | ✅ |
| **yaml-language-server** | YAML | ✅ |
| **vscode-langservers-extracted** | HTML, CSS, JSON, ESLint | |
| **gh-actions-language-server** | GitHub Actions | |
| **lua-language-server** | Lua | |

**Check installed**:

```bash
npm list -g --depth=0 | grep language-server
```

---

## Linters & Formatters

### Python (via uv)

| Tool | Purpose | In Registry |
|------|---------|-------------|
| **ruff** | Linter & formatter (replaces flake8, black, isort) | ✅ |
| **mypy** | Static type checker | ✅ |
| **basedpyright** | Type checker (Pyright fork) | ✅ |
| **codespell** | Spell checker for code | |
| **sqlfluff** | SQL linter | |
| **mdformat** | Markdown formatter | |

### JavaScript/TypeScript (via npm)

| Tool | Purpose | In Registry |
|------|---------|-------------|
| **prettier** | Code formatter (multi-language) | ✅ |
| **prettierd** | Prettier daemon (faster) | |
| **eslint** | JavaScript/TypeScript linter | ✅ |
| **markdownlint-cli** | Markdown linter | |

### Shell (via brew)

| Tool | Purpose | In Registry |
|------|---------|-------------|
| **shellcheck** | Shell script linter | ✅ |
| **shfmt** | Shell script formatter | ✅ |

### Other (via brew)

| Tool | Purpose |
|------|---------|
| **taplo** | TOML formatter & linter |
| **actionlint** | GitHub Actions linter |

---

## Containerization & Infrastructure

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **docker** | cask | Docker Desktop (GUI) | ✅ |
| **lazydocker** | brew | Docker TUI | ✅ |
| **oxker** | brew | Docker container viewer TUI | |

---

## Cloud & DevOps

### Terraform Ecosystem

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **terraform** | brew | Infrastructure as Code | ✅ |
| **terraform-docs** | brew | Generate Terraform docs | |
| **terraform-ls** | brew | Terraform language server | |
| **terraformer** | brew | Import existing infrastructure | |
| **terrascan** | brew | Terraform security scanner | |
| **tflint** | brew | Terraform linter | |

### Cloud

| Tool | Install | Description |
|------|---------|-------------|
| **awscli** | brew | AWS command-line interface |

### Security

| Tool | Install | Description |
|------|---------|-------------|
| **trivy** | brew | Container vulnerability scanner |
| **mkcert** | brew | Local SSL certificates |
| **gnupg** | brew | GPG encryption |
| **gpg-tui** | brew | GPG terminal UI |

---

## Database Tools

| Tool | Install | Description |
|------|---------|-------------|
| **postgresql@16** | brew | PostgreSQL database |
| **pgloader** | brew | PostgreSQL data loader |
| **dbeaver-community** | cask | Universal database GUI |

---

## Build & Task Automation

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **task** | brew | Modern Taskfile runner | ✅ |
| **supervisor** | brew | Process control system | |

---

## System Utilities

### Process & Monitoring

| Tool | Install | Description | In Registry |
|------|---------|-------------|-------------|
| **htop** | brew | Interactive process viewer | ✅ |
| **watch** | brew | Execute program periodically | |
| **coretemp** | brew | CPU temperature monitoring | |

### Archive & Compression

| Tool | Install | Description |
|------|---------|-------------|
| **sevenzip** | brew | 7zip compression |
| **gnu-tar** | brew | GNU tar (available as `gtar`) |

### Network

| Tool | Install | Description |
|------|---------|-------------|
| **curl** | brew | Transfer data with URLs |
| **wget** | brew | File retrieval |
| **nmap** | brew | Network scanner |

### Other

| Tool | Install | Description |
|------|---------|-------------|
| **coreutils** | brew | GNU coreutils (g-prefixed) |
| **findutils** | brew | GNU findutils |
| **nginx** | brew | Web server |

---

## Media & Graphics

| Tool | Install | Description |
|------|---------|-------------|
| **ffmpeg** | brew | Video/audio processing |
| **mpv** | brew | Media player |
| **yt-dlp** | brew | YouTube downloader |
| **imagemagick** | brew | Image processing |
| **graphviz** | brew | Graph visualization |
| **gource** | brew | Repository visualization |

---

## macOS-Specific

### Window Management

| Tool | Install | Description |
|------|---------|-------------|
| **aerospace** | cask | Tiling window manager |
| **borders** | brew | Window border highlights |
| **sketchybar** | brew | Custom menubar |

### Applications

| Tool | Install | Description |
|------|---------|-------------|
| **alfred** | cask | Launcher & productivity |
| **bettertouchtool** | cask | Input customization |
| **ghostty** | manual | Terminal emulator |
| **iterm2** | cask | Terminal emulator |
| **macs-fan-control** | cask | Fan control |
| **michaelvillar-timer** | cask | Timer app |
| **multipass** | cask | Ubuntu VM manager |
| **obsidian** | cask | Note taking |
| **slack** | cask | Team chat |
| **discord** | cask | Chat |
| **zoom** | cask | Video conferencing |

### System

| Tool | Install | Description |
|------|---------|-------------|
| **mas** | brew | Mac App Store CLI |

---

## Fun & Demo

| Tool | Install | Description |
|------|---------|-------------|
| **cmatrix** | brew | Matrix effect |
| **figlet** | brew | ASCII art text |
| **pipes-sh** | brew | Animated pipes |
| **sl** | brew | Steam locomotive joke |

**Try them**:

```bash
cmatrix        # Ctrl+C to exit
echo "DOTFILES" | figlet
pipes-sh
sl
```

---

## Installation Summary

### By Package Manager

- **Homebrew** (brew): ~80 packages
- **Homebrew Casks**: ~15 GUI applications
- **npm** (via nvm): 11 global packages
- **uv tools**: 9 Python tools
- **Cargo**: 1 package (uv)
- **Script/Manual**: nvm, ghostty

### By Category

- **Development Tools**: 40+
- **System Utilities**: 20+
- **Infrastructure/DevOps**: 15+
- **Media & Graphics**: 6
- **macOS Applications**: 12+
- **Fun/Demo**: 4

---

## Quick Reference

### Discover Tools

```bash
tools list                  # List all tools in registry
tools categories            # Show categories
tools show bat              # Detailed info on bat
tools search git            # Find git-related tools
tools random                # Discover a random tool
```

### Check Installed

```bash
brew list                   # Homebrew packages
npm list -g --depth=0      # npm global packages
uv tool list               # uv-installed tools
```

### Update Everything

```bash
task update                # Update all (when Taskfile created)
brew update && brew upgrade
npm update -g
uv self update
```

---

## Notes

### Tools Not in PATH by Default

**GNU Coreutils** (available with `g` prefix):

- `gls`, `gsed`, `gtar`, `ggrep`, etc.
- Prevents conflicts with macOS system tools
- See `brew --prefix coreutils` for location

### Deprecated Tools

None currently. All tools are actively maintained.

### Considering for Removal

Run periodically to check for unused tools:

```bash
tools-stats unused          # Tools not used in 30 days (when implemented)
```

---

**Next Steps**: Use the `tools` command to explore and learn about installed tools. See `docs/tools/registry.yml` for detailed documentation.
