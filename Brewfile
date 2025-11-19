# ================================================================
# Homebrew Bundle File
# ================================================================
# Managed by Taskfile - changes committed automatically
# Platform: macOS
# Last auto-generated: 2025-11-04

# ================================================================
# TAPS
# ================================================================
tap "homebrew/bundle"
tap "homebrew/cask"
tap "homebrew/cask-fonts"
tap "homebrew/core"

# ================================================================
# CORE DEVELOPMENT TOOLS
# ================================================================
# Modern CLI replacements and essential dev tools
# NOTE: See management/packages.yml for tools installed via:
#   - Cargo: bat, eza, fd, zoxide, git-delta, tinty
#   - GitHub releases: neovim, fzf, lazygit, yazi, go
#   - npm: language servers, linters
#   - uv: Python tools
brew "ripgrep"          # ultra-fast grep
brew "git"              # version control
brew "gh"               # GitHub CLI
brew "tmux"             # terminal multiplexer
brew "jq"               # JSON processor

# ================================================================
# VERSION CONTROL & GIT TOOLS
# ================================================================
brew "git-secrets"      # prevent committing secrets

# ================================================================
# FILE MANAGEMENT & VIEWING
# ================================================================
brew "tree"             # directory tree visualization
brew "duf"              # modern df alternative
brew "duti"             # macOS file association manager
brew "glow"             # markdown renderer

# ================================================================
# SEARCH & TEXT PROCESSING
# ================================================================
brew "grep"             # GNU grep
brew "gnu-sed"          # GNU sed (available as gsed)

# ================================================================
# PROGRAMMING LANGUAGES
# ================================================================
# NOTE: Python managed by uv, Node.js managed by nvm, Go via GitHub (see packages.yml)
brew "ruby"             # Ruby programming language
brew "lua"              # Lua scripting language
brew "luajit"           # LuaJIT compiler
brew "luarocks"         # Lua package manager
brew "sbcl"             # Steel Bank Common Lisp

# ================================================================
# LANGUAGE SERVERS
# ================================================================
# NOTE: Most LSPs installed via npm, see config/packages.yml
brew "lua-language-server"  # Lua LSP

# ================================================================
# LINTERS & FORMATTERS
# ================================================================
# Shell
brew "shellcheck"       # shell script linter
brew "shfmt"            # shell script formatter

# Other
brew "taplo"            # TOML formatter & linter
brew "actionlint"       # GitHub Actions linter

# ================================================================
# CONTAINERIZATION & INFRASTRUCTURE
# ================================================================
brew "lazydocker"       # docker TUI
brew "oxker"            # docker container viewer TUI

# Terraform ecosystem
brew "terraform"        # infrastructure as code
brew "terraform-docs"   # generate terraform docs
brew "terraform-ls"     # terraform language server
brew "terraformer"      # import existing infrastructure
brew "terrascan"        # terraform security scanner
brew "tflint"           # terraform linter

# ================================================================
# CLOUD & DEVOPS
# ================================================================
brew "awscli"           # AWS command-line interface

# ================================================================
# SECURITY
# ================================================================
brew "mkcert"           # local SSL certificates
brew "gnupg"            # GPG encryption
brew "gpg-tui"          # GPG terminal UI
brew "trivy"            # container vulnerability scanner

# ================================================================
# DATABASE TOOLS
# ================================================================
brew "postgresql@16"    # PostgreSQL database

# ================================================================
# BUILD & TASK AUTOMATION
# ================================================================
brew "go-task"          # modern taskfile runner
brew "supervisor"       # process control system

# ================================================================
# SYSTEM UTILITIES
# ================================================================
# Process & Monitoring
brew "htop"             # interactive process viewer
brew "watch"            # execute program periodically
brew "coretemp"         # CPU temperature monitoring

# Archive & Compression
brew "sevenzip"         # 7zip compression
brew "gnu-tar"          # GNU tar (available as gtar)

# Network
brew "curl"             # transfer data with URLs
brew "wget"             # file retrieval
brew "nmap"             # network scanner

# Core utilities
brew "coreutils"        # GNU coreutils (g-prefixed, not in PATH)
brew "findutils"        # GNU findutils

# macOS specific
brew "mas"              # Mac App Store CLI

# ================================================================
# MEDIA & GRAPHICS
# ================================================================
brew "ffmpeg"           # video/audio processing
brew "mpv"              # media player
brew "yt-dlp"           # YouTube downloader
brew "imagemagick"      # image processing
brew "graphviz"         # graph visualization
brew "gource"           # repository visualization

# ================================================================
# FUN & DEMO
# ================================================================
brew "figlet"           # ASCII art text

# ================================================================
# MACOS-SPECIFIC TOOLS
# ================================================================
brew "borders"          # window border highlights
brew "sketchybar"       # custom menubar
brew "terminal-notifier" # macOS notifications from terminal

# ================================================================
# TERMINAL & SHELL
# ================================================================
brew "bash"             # updated bash shell
brew "tmuxinator"       # tmux session manager
brew "tmuxinator-completion" # tmux completion

# ================================================================
# MACOS GUI APPLICATIONS (Casks)
# ================================================================

# Window Management
cask "aerospace"        # tiling window manager

# Productivity
cask "alfred"           # launcher & productivity
cask "bettertouchtool"  # input customization

# Development
cask "dbeaver-community" # universal database GUI

# Utilities
cask "macs-fan-control" # fan control
cask "michaelvillar-timer" # timer app
cask "multipass"        # Ubuntu VM manager

# Communication
cask "discord"          # chat
cask "slack"            # team chat
cask "zoom"             # video conferencing

# Notes & Knowledge
cask "obsidian"         # note taking

# ================================================================
# NOTES
# ================================================================
# Cross-platform packages defined in management/packages.yml:
#   - Parsed by management/parse-packages.py (Python script)
#   - Cargo tools: bat, eza, fd, zoxide, git-delta, tinty
#   - GitHub binaries: neovim, fzf, lazygit, yazi, go
#   - npm packages: language servers, linters (see packages.yml)
#   - uv tools: Python linters, formatters (see packages.yml)
#
# macOS-specific notes:
#   - ghostty terminal installed manually (not in Homebrew)
#   - docker-desktop managed separately (large cask)
#   - Fonts managed manually in ~/fonts directory
#   - GNU coreutils NOT in PATH (available with g-prefix)
#   - Node.js managed by nvm (not brew)
#   - Python development managed by uv (not brew)
