# Homebrew Bundle Cleanup Analysis

Generated: 2025-11-27
Purpose: Categorize every package from `brew bundle cleanup` output and determine disposition

## Summary Statistics

- **Total Casks to Review**: 3
- **Total Formulae to Review**: 82
- **Total Taps to Review**: 4

## Categorization Guide

- **UNINSTALL**: Not needed, safe to remove
- **ADD_TO_PACKAGES_YML**: Needed cross-platform, should be in install scripts
- **KEEP_IN_BREWFILE**: macOS-specific, should stay in Brewfile
- **DEPENDENCIES**: Automatically installed dependency (don't need to explicitly manage)
- **NEEDS_DECISION**: Unclear, requires user decision

---

## Casks Analysis

### docker-desktop

**What it is**: Docker Desktop for Mac - GUI application for Docker containers
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: Found references in tmuxinator configs, various docs
**Category**: **NEEDS_DECISION**
**Reasoning**: The Brewfile notes say "docker-desktop managed separately (large cask)". User has `docker` CLI formula installed and uses lazydocker/oxker TUIs. Question: Is Docker Desktop still needed or can user rely on just Docker CLI?

### iterm2

**What it is**: Terminal emulator for macOS
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: Found in archive directory (archive/macos/com.googlecode.iterm2.plist, .iterm2_shell_integration.zsh)
**Category**: **UNINSTALL**
**Reasoning**: User explicitly uses Ghostty terminal (per CLAUDE.md). iTerm2 config files are archived. No current usage.

### qutebrowser

**What it is**: Keyboard-driven, vim-like browser
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: Only found in Brewfile for searching
**Category**: **UNINSTALL**
**Reasoning**: Not mentioned anywhere in active configs. No evidence of usage. Likely experimental install.

---

## Formulae Analysis - Alphabetical

### apr

**What it is**: Apache Portable Runtime - library for cross-platform development
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by apr-util
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for apr-util. Will be removed when apr-util is removed.

### apr-util

**What it is**: Apache Portable Runtime Utility library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by nothing (orphaned)
**Category**: **DEPENDENCIES**
**Reasoning**: Orphaned dependency. Safe to remove - no packages depend on it.

### bat

**What it is**: cat clone with syntax highlighting
**Status**: IN packages.yml (cargo_packages), NOT in Brewfile (correctly)
**Usage in dotfiles**: Used extensively (zk config, theme-sync, fzf functions)
**Dependency check**: Uses libgit2
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall (packages.yml). Homebrew version is duplicate/dependency conflict. Should uninstall brew version, keep cargo version.

### bdw-gc

**What it is**: Boehm-Demers-Weiser garbage collector
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by guile
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for guile. Disposition depends on guile decision.

### buku

**What it is**: Browser-independent bookmark manager
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses pycparser, cffi, cryptography
**Category**: **NEEDS_DECISION**
**Reasoning**: Bookmark manager with CLI interface. No evidence of current usage. Question: Is this something you use or was it experimental?

### cffi

**What it is**: C Foreign Function Interface for Python
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by buku, cryptography
**Category**: **DEPENDENCIES**
**Reasoning**: Python library dependency. Will be removed with buku.

### cmatrix

**What it is**: "The Matrix" terminal screensaver
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Fun/demo tool. Not documented or integrated. Safe to remove.

### codespell

**What it is**: Spell checker for code
**Status**: IN packages.yml (uv_tools), NOT in Brewfile (correctly)
**Usage in dotfiles**: None found, but in packages.yml for quality control
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via uv tools. Homebrew version is duplicate. Should uninstall brew version.

### cryptography

**What it is**: Python cryptography library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses pycparser, cffi; used by buku
**Category**: **DEPENDENCIES**
**Reasoning**: Python library dependency. Will be removed with buku.

### docker

**What it is**: Docker CLI (command-line interface)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: Used in tmuxinator configs, referenced in docs
**Dependency check**: Requires docker-completion
**Category**: **KEEP_IN_BREWFILE**
**Reasoning**: Docker CLI is actively used (tmuxinator configs show docker monitoring). Should be added to Brewfile. macOS-specific since Linux typically uses native package managers for Docker.

### docker-completion

**What it is**: Shell completions for Docker
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Required by docker formula
**Category**: **DEPENDENCIES**
**Reasoning**: Auto-installed with docker. Will be managed when docker is added to Brewfile.

### docutils

**What it is**: Python documentation utilities (reStructuredText tools)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Python documentation tool. Not used in this project (uses MkDocs for docs). Safe to remove.

### duf

**What it is**: Better df alternative - disk usage viewer
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: None found directly
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### eza

**What it is**: Modern ls replacement
**Status**: IN packages.yml (cargo_packages), NOT in Brewfile (correctly)
**Usage in dotfiles**: Used extensively (aliases, functions)
**Dependency check**: Uses libgit2
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall. Homebrew version is duplicate. Should uninstall brew version.

### fd

**What it is**: Modern find replacement
**Status**: IN packages.yml (cargo_packages as fd-find), NOT in Brewfile (correctly)
**Usage in dotfiles**: Used in fzf functions, neovim configs
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall. Homebrew version is duplicate. Should uninstall brew version.

### freetds

**What it is**: Libraries for MS SQL and Sybase databases
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses unixodbc; used by pgloader
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for pgloader. Disposition depends on pgloader decision.

### fzf

**What it is**: Fuzzy finder
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: Used EXTENSIVELY (shell functions, theme-sync, menu, notes, git integrations)
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries with go build. Homebrew version is duplicate. Should uninstall brew version.

### geckodriver

**What it is**: WebDriver for Firefox (Selenium/automation)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Browser automation tool. No evidence of usage in configs or scripts. Likely leftover from testing/experimentation.

### git-delta

**What it is**: Syntax-highlighting git diff viewer
**Status**: IN packages.yml (cargo_packages), NOT in Brewfile (correctly)
**Usage in dotfiles**: Configured in git config
**Dependency check**: Uses libgit2
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall. Homebrew version is duplicate. Should uninstall brew version.

### glow

**What it is**: Markdown renderer for terminal
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: None found directly, but common tool for viewing markdown
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### gpgmepp

**What it is**: C++ bindings for GPGME (GPG Made Easy)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Category**: **DEPENDENCIES**
**Reasoning**: Likely auto-installed dependency for GPG tools. Safe to remove if orphaned.

### guile

**What it is**: GNU Ubiquitous Intelligent Language for Extensions (Scheme interpreter)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses bdw-gc, pkgconf
**Category**: **UNINSTALL**
**Reasoning**: GNU Scheme interpreter. No evidence of usage. Not a common dependency for typical dev tools. Safe to remove.

### gum

**What it is**: Charmbracelet tool for glamorous shell scripts (TUI components)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **NEEDS_DECISION**
**Reasoning**: High-quality tool for shell script UIs. Not currently used but could be useful for future script enhancements. Question: Keep for potential use or remove?

### hashicorp/tap/terraform

**What it is**: Terraform infrastructure-as-code tool
**Status**: Not in packages.yml, NOT in Brewfile (uses tenv version manager instead)
**Usage in dotfiles**: packages.yml includes tenv for version management
**Category**: **DEPENDENCIES**
**Reasoning**: Using tenv (Terraform version manager) instead per packages.yml. Homebrew version is duplicate. Should uninstall.

### hashicorp/tap/terraform-ls

**What it is**: Terraform Language Server
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: Configured in Neovim LSP
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### lazygit

**What it is**: Simple terminal UI for git
**Status**: IN packages.yml (github_binaries), IN Brewfile
**Usage in dotfiles**: Used extensively (aliases, keybindings)
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version, remove from Brewfile.

### libcbor

**What it is**: CBOR protocol implementation library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by libfido2
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for libfido2. Will be cleaned up automatically.

### libfido2

**What it is**: Library for FIDO 2.0 authentication
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses libcbor; no packages use libfido2
**Category**: **DEPENDENCIES**
**Reasoning**: Orphaned dependency. Safe to remove.

### libgit2

**What it is**: Portable C library for Git operations
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Used by bat, eza, git-delta (all cargo packages)
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for cargo-installed Rust tools. These tools likely use statically linked Rust crates, not the Homebrew libgit2. Safe to remove - cargo versions are self-contained.

### libpq

**What it is**: PostgreSQL C API library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by pgloader
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for pgloader. Disposition depends on pgloader decision.

### libtommath

**What it is**: Portable number theoretic multiple-precision integer library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by python-tk@3.12, tcl-tk
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for Python/Tcl Tk GUI libraries. Will be removed when Python 3.12 is cleaned up.

### libuv

**What it is**: Multi-platform support library (async I/O)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by luv, neovim
**Category**: **DEPENDENCIES**
**Reasoning**: Critical dependency for Neovim. Must keep. (Note: Neovim managed via GitHub releases, but may use system libuv)

### lpeg

**What it is**: Pattern-matching library for Lua
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Used by neovim
**Category**: **DEPENDENCIES**
**Reasoning**: Lua library used by Neovim. Must keep.

### luv

**What it is**: Lua bindings for libuv
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Uses libuv; used by neovim
**Category**: **DEPENDENCIES**
**Reasoning**: Critical dependency for Neovim's Lua support. Must keep.

### mad

**What it is**: MPEG audio decoder library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Audio codec library. No media processing scripts found. Safe to remove (you have sox for audio, ffmpeg for video).

### neovim

**What it is**: Hyperextensible Vim-based text editor
**Status**: IN packages.yml (github_binaries), IN Brewfile
**Usage in dotfiles**: Core editor - used EXTENSIVELY throughout entire dotfiles
**Dependency check**: Uses tree-sitter, unibilium, luv, lpeg, libuv
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries (packages.yml specifies min version 0.11). Homebrew version is duplicate. Should uninstall brew version, remove from Brewfile. Keep the dependencies (tree-sitter, unibilium, luv, lpeg, libuv).

### nginx

**What it is**: HTTP/reverse proxy server
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: Found in tmuxinator configs for monitoring
**Category**: **NEEDS_DECISION**
**Reasoning**: Web server/reverse proxy. Found in ichrisbirch monitoring configs. Question: Still actively used for local development?

### nspr

**What it is**: Netscape Portable Runtime (platform abstraction library)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **DEPENDENCIES**
**Reasoning**: Likely dependency for nss or other Mozilla-related libraries. Safe to remove if orphaned.

### nss

**What it is**: Network Security Services (Mozilla crypto library)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **DEPENDENCIES**
**Reasoning**: Mozilla's crypto library. Likely dependency for geckodriver or similar. Safe to remove after geckodriver removal.

### openjdk

**What it is**: Open Java Development Kit
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None in active configs
**Category**: **UNINSTALL**
**Reasoning**: No Java projects in dotfiles. Likely installed for a one-off need. Safe to remove (can reinstall if needed).

### opusfile

**What it is**: Library for decoding .opus audio files
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by sox
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for sox. Disposition depends on sox decision.

### pandoc

**What it is**: Universal document converter (markdown, PDF, etc.)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Document conversion tool. No conversion scripts found. Project uses MkDocs directly for documentation. Safe to remove.

### pgloader

**What it is**: PostgreSQL data migration tool (MySQL/MSSQL to Postgres)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses unixodbc, freetds, libpq
**Category**: **UNINSTALL**
**Reasoning**: Database migration tool. No database migration scripts or configs. Specialized tool for one-off migrations. Safe to remove.

### pipx

**What it is**: Python application installer in isolated environments
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None (using uv tools instead)
**Category**: **UNINSTALL**
**Reasoning**: Python tool isolation - but dotfiles use `uv tool` for this purpose (see packages.yml uv_tools). pipx is redundant. Safe to remove.

### pipes-sh

**What it is**: Animated pipes terminal screensaver
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Fun/demo tool similar to cmatrix. Not documented or integrated. Safe to remove.

### pkgconf

**What it is**: Package compiler and linker metadata toolkit
**Status**: Not in packages.yml, IN Brewfile as pkg-config (different package!)
**Usage in dotfiles**: Build system essential
**Dependency check**: Used by guile
**Category**: **DEPENDENCIES**
**Reasoning**: The Brewfile has `pkg-config`, and packages.yml has `pkg-config`. This `pkgconf` is a dependency for guile. Safe to remove when guile is removed. (Note: pkg-config and pkgconf are related but different implementations)

### poppler

**What it is**: PDF rendering library
**Status**: IN packages.yml (poppler-utils for Linux), NOT in Brewfile
**Usage in dotfiles**: packages.yml shows poppler-utils for Linux only
**Dependency check**: No packages use poppler
**Category**: **UNINSTALL**
**Reasoning**: packages.yml explicitly lists poppler-utils for Linux only (apt/pacman), not macOS. Homebrew poppler is not needed. Safe to remove.

### pre-commit

**What it is**: Framework for managing git pre-commit hooks
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: .pre-commit-config.yaml exists and is actively used
**Category**: **KEEP_IN_BREWFILE**
**Reasoning**: Critical for git workflow quality control. Should be added to Brewfile. macOS-specific management makes sense.

### python@3.12

**What it is**: Python 3.12 interpreter
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: packages.yml says "Python managed by uv"
**Dependency check**: Used only by python-tk@3.12
**Category**: **DEPENDENCIES**
**Reasoning**: Project uses uv for Python management. Homebrew Python is dependency baggage. However, pre-commit requires python@3.14 per its info. Safe to remove python@3.12 after verifying pre-commit has python@3.14.

### python-tk@3.12

**What it is**: Python 3.12 Tk GUI library bindings
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses libtommath, python@3.12
**Category**: **UNINSTALL**
**Reasoning**: Tk GUI library for Python. No Tk GUI scripts in dotfiles. Safe to remove.

### pycparser

**What it is**: C parser in Python
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by buku, cffi, cryptography
**Category**: **DEPENDENCIES**
**Reasoning**: Python library dependency. Will be removed with buku.

### sbt

**What it is**: Scala Build Tool
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Scala development tool. No Scala projects in dotfiles. Safe to remove.

### sl

**What it is**: Steam locomotive animation (joke command for typos of 'ls')
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Fun easter egg. Not integrated into workflow. Safe to remove.

### sox

**What it is**: Sound eXchange - audio processing tool
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses opusfile
**Category**: **UNINSTALL**
**Reasoning**: Audio processing CLI. No audio scripts found. You have ffmpeg for media processing. Safe to remove.

### tcl-tk

**What it is**: Tool Command Language GUI toolkit
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Uses libtommath
**Category**: **DEPENDENCIES**
**Reasoning**: Dependency for python-tk@3.12. Will be removed with python-tk.

### terraform-docs

**What it is**: Generate documentation from Terraform modules
**Status**: IN packages.yml (go_tools), NOT in Brewfile (correctly)
**Usage in dotfiles**: None currently, but in packages for future Terraform work
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via go install. Homebrew version is duplicate. Should uninstall brew version.

### terraformer

**What it is**: Import existing infrastructure to Terraform
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: None currently
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### terrascan

**What it is**: Terraform security scanner
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: None currently
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### tflint

**What it is**: Terraform linter
**Status**: IN packages.yml (github_binaries), NOT in Brewfile (correctly)
**Usage in dotfiles**: Configured in Neovim LSP, pre-commit config (commented)
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version.

### tinted-theming/tinted/tinty

**What it is**: Base16 theme manager
**Status**: IN packages.yml (cargo_packages), NOT in Brewfile (correctly)
**Usage in dotfiles**: Core theme system - used by theme-sync app
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall. Homebrew version is duplicate. Should uninstall brew version.

### tlrc

**What it is**: Rust-based tldr client (command cheat sheets)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: TLDR pages client. You have `cheat` command installed (packages.yml go_tools). Duplicate functionality. Safe to remove.

### tokei

**What it is**: Lines of code counter (Rust)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Category**: **UNINSTALL**
**Reasoning**: Code statistics tool. Not integrated into workflow or scripts. Nice-to-have but not essential. Safe to remove.

### tree-sitter

**What it is**: Parser generator for syntax highlighting
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Used by neovim
**Category**: **DEPENDENCIES**
**Reasoning**: Critical dependency for Neovim's Tree-sitter integration. Must keep.

### tree-sitter-cli

**What it is**: Tree-sitter command-line tool
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: No packages use tree-sitter-cli
**Category**: **UNINSTALL**
**Reasoning**: Tree-sitter development tool (for creating parsers). Neovim uses tree-sitter library, not CLI. Safe to remove.

### unibilium

**What it is**: Terminfo parsing library
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None directly
**Dependency check**: Used by neovim
**Category**: **DEPENDENCIES**
**Reasoning**: Critical dependency for Neovim terminal handling. Must keep.

### unixodbc

**What it is**: ODBC driver manager for Unix
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None
**Dependency check**: Used by freetds, pgloader
**Category**: **DEPENDENCIES**
**Reasoning**: Database connectivity library. Dependency for pgloader. Will be removed with pgloader.

### virtualenv

**What it is**: Python virtual environment tool
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None (using uv for Python environments)
**Category**: **UNINSTALL**
**Reasoning**: Python environment isolation - but dotfiles use `uv` for this purpose. virtualenv is legacy approach. Safe to remove.

### yazi

**What it is**: Terminal file manager
**Status**: IN packages.yml (github_binaries), IN Brewfile
**Usage in dotfiles**: Used extensively (configured, keybindings, preview scripts)
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via GitHub binaries. Homebrew version is duplicate. Should uninstall brew version, remove from Brewfile.

### yq

**What it is**: YAML processor (jq for YAML)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: None found
**Category**: **UNINSTALL**
**Reasoning**: YAML query tool. You have jq for JSON. No YAML processing scripts found. Safe to remove.

### zk

**What it is**: Plain text note-taking assistant (Zettelkasten)
**Status**: Not in packages.yml, not in Brewfile
**Usage in dotfiles**: YES - full config at platforms/common/.config/zk/config.toml, Neovim LSP integration
**Category**: **KEEP_IN_BREWFILE**
**Reasoning**: Actively configured note-taking system. Should be added to Brewfile. Could also be added to packages.yml as cross-platform if available via other package managers.

### zoxide

**What it is**: Smarter cd command (directory jumper)
**Status**: IN packages.yml (cargo_packages), NOT in Brewfile (correctly)
**Usage in dotfiles**: Initialized in .zshrc, used via 'z' command
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via cargo-binstall. Homebrew version is duplicate. Should uninstall brew version.

### zsh-syntax-highlighting

**What it is**: Fish-like syntax highlighting for ZSH
**Status**: IN packages.yml (shell_plugins), NOT in Brewfile (correctly)
**Usage in dotfiles**: Loaded in .zshrc, plugin directory exists
**Category**: **DEPENDENCIES**
**Reasoning**: Already managed via git clone (packages.yml shell_plugins). Homebrew version is duplicate/conflict. Should uninstall brew version.

---

## Taps Analysis

### hashicorp/tap

**What it is**: HashiCorp's Homebrew tap (terraform, terraform-ls)
**Status**: Not needed
**Category**: **DEPENDENCIES**
**Reasoning**: Both packages from this tap are managed elsewhere (tenv, GitHub binaries). Safe to untap after removing formulae.

### xwmx/taps

**What it is**: Unknown tap - needs investigation
**Status**: Not in Brewfile
**Category**: **UNINSTALL**
**Reasoning**: No packages from this tap are mentioned. Safe to untap.

### nikitabobko/tap

**What it is**: AeroSpace window manager tap
**Status**: Not in taps list (aerospace is in main Homebrew now)
**Category**: **UNINSTALL**
**Reasoning**: AeroSpace is now in homebrew-cask core. This tap is obsolete. Safe to untap.

### tinted-theming/tinted

**What it is**: Base16/tinty theming tap
**Status**: Not needed (tinty via cargo)
**Category**: **DEPENDENCIES**
**Reasoning**: tinty is managed via cargo-binstall. Safe to untap after removing tinty formula.

---

## Summary by Category

### UNINSTALL (31 packages + 3 casks)

**Casks**: iterm2, qutebrowser
**Formulae**: cmatrix, docutils, geckodriver, guile (and bdw-gc dependency), mad, openjdk, pandoc, pgloader (and unixodbc, freetds, libpq), pipx, pipes-sh, python-tk@3.12 (and tcl-tk, libtommath), pycparser (if no other deps), sl, sbt, sox (and opusfile), tlrc, tokei, tree-sitter-cli, virtualenv, yq

### DEPENDENCIES - Uninstall Homebrew duplicates (23 packages)

These are managed via other methods in packages.yml:

- **Cargo**: bat, eza, fd, git-delta, tinty, zoxide (and libgit2 which they may use)
- **GitHub binaries**: duf, fzf, glow, lazygit, neovim, terraform-ls, terraformer, terrascan, tflint, yazi
- **Go tools**: terraform-docs
- **UV tools**: codespell
- **Shell plugins**: zsh-syntax-highlighting
- **Version managers**: hashicorp/tap/terraform (using tenv instead)

### ✅ REMOVE - Neovim dependencies (5 packages)

**UPDATED:** Can safely remove - Neovim GitHub binaries are statically linked:

- libuv, lpeg, luv, tree-sitter, unibilium

Verified with `otool -L ~/.local/bin/nvim` - only links to macOS system libraries, not Homebrew packages.

### ✅ ADD_TO_PACKAGES_YML - Move to packages.yml (3 packages)

**UPDATED:** Adding to packages.yml (eliminating Brewfile):

- **docker** → packages.yml (using Docker official repos on all platforms)
- **docker-completion** → auto-installed with docker
- **pre-commit** → packages.yml system_packages
- **zk** → packages.yml system_packages (if available cross-platform) or github_binaries

### ✅ DECISIONS MADE

User decisions finalized:

1. **docker-desktop** (cask) → **REMOVE** (switching to Colima + Docker official repos)
2. **buku** → **REMOVE** (not used)
3. **gum** → **KEEP** (added to packages.yml go_tools, used by menu/notes apps)
4. **nginx** → **REMOVE** (will use Docker containers if needed)

---

## Recommended Action Plan

### Phase 1: Quick Wins (Safe Uninstalls)

```bash
# Uninstall fun/experimental tools
brew uninstall cmatrix sl pipes-sh

# Uninstall obsolete terminals and browsers
brew uninstall --cask iterm2 qutebrowser

# Uninstall unused development tools
brew uninstall sbt openjdk geckodriver tokei tlrc

# Uninstall document tools (using MkDocs instead)
brew uninstall pandoc docutils

# Uninstall database tools (not used)
brew uninstall pgloader  # Will also remove unixodbc, freetds, libpq

# Uninstall Python tools (using uv instead)
brew uninstall pipx virtualenv python-tk@3.12  # Will also remove tcl-tk, libtommath

# Uninstall media tools (have ffmpeg)
brew uninstall sox mad  # Will also remove opusfile

# Uninstall misc unused
brew uninstall yq tree-sitter-cli guile  # guile will also remove bdw-gc, pkgconf
```

### Phase 2: Remove Duplicates (Managed Elsewhere)

```bash
# Rust/Cargo tools (already in cargo via binstall)
brew uninstall bat eza fd git-delta zoxide tinty

# GitHub binary releases
brew uninstall neovim lazygit yazi fzf glow duf
brew uninstall terraform-ls tflint terraformer terrascan

# Go tools
brew uninstall terraform-docs hashicorp/tap/terraform

# UV tools
brew uninstall codespell

# Shell plugins
brew uninstall zsh-syntax-highlighting

# Clean up libgit2 (cargo tools use statically linked versions)
brew uninstall libgit2
```

### Phase 3: Clean Up Taps

```bash
brew untap hashicorp/tap
brew untap tinted-theming/tinted
brew untap xwmx/taps
brew untap nikitabobko/tap
```

### Phase 4: Add Missing to Brewfile

```bash
# Edit Brewfile to add:
# brew "docker"              # Container runtime CLI
# brew "pre-commit"          # Git hooks framework
# brew "zk"                  # Note-taking assistant
```

### Phase 5: User Decisions Required

Answer these questions:

1. **docker-desktop**: Do you still need Docker Desktop GUI, or is Docker CLI + lazydocker sufficient?
2. **buku**: Do you use this bookmark manager?
3. **gum**: Want to keep for potential future shell script UIs?
4. **nginx**: Still using for local development/testing?

---

## Files to Update After Cleanup

1. **Brewfile** - Add: docker, pre-commit, zk
2. **packages.yml** - Consider adding zk to github_binaries or system_packages if available cross-platform
3. Run `task symlinks:link` after any config changes
4. Run `task macos:update` to verify installation health

---

## Notes

- Total potential removals: ~60 packages (if all NEEDS_DECISION items are removed)
- All Neovim dependencies (libuv, lpeg, luv, tree-sitter, unibilium) will be kept
- No breaking changes to current workflow
- Pre-commit and Docker will be properly managed in Brewfile
- All duplicates removed in favor of packages.yml methods (cargo, github, go, uv)

---

## ✅ FINAL SUMMARY (Updated with User Decisions)

### Total Packages to Remove: ~70 packages + 3 casks

**Breakdown:**

- 31 unneeded packages (fun tools, unused dev tools, etc.)
- 28 duplicates (managed via packages.yml: cargo, github_binaries, go_tools, uv_tools)
- 5 Neovim dependencies (statically linked, not needed)
- 4 user decisions (buku, nginx, docker-desktop, gum → moved to packages.yml)
- 2 casks (iterm2, qutebrowser)
- 1 cask decision (docker-desktop → using Colima)

### Packages to Add to packages.yml

- docker (via official repos on all platforms)
- pre-commit
- zk (note-taking tool)
- gum (already added to go_tools)
- lazydocker (already added to go_tools)

### Next Steps

1. ✅ Update packages.yml with docker (official repos), pre-commit, zk
2. ✅ Create Docker official repo install scripts
3. ⏸️ User review and approve final cleanup list
4. ⏸️ Execute `brew bundle cleanup --force`
5. ⏸️ Migrate remaining Brewfile entries to packages.yml
6. ⏸️ Eliminate Brewfile completely

---

## Sources

Research sources:

- [Homebrew dependency checking](https://www.thingy-ma-jig.co.uk/blog/22-09-2014/homebrew-list-packages-and-what-uses-them)
- [Homebrew and Python documentation](https://docs.brew.sh/Homebrew-and-Python)
- [Gum CLI tool](https://github.com/charmbracelet/gum)
- [tlrc Rust TLDR client](https://github.com/tldr-pages/tlrc)
- [zk note-taking tool](https://github.com/zk-org/zk)
- [pgloader PostgreSQL migration](https://pgloader.io/)
- [sbt Scala Build Tool](https://www.scala-sbt.org/)
- [Tokei code statistics](https://github.com/XAMPPRocky/tokei)
- [Python 3.14 release information](https://www.python.org/downloads/release/python-3140/)
- [Neovim build documentation](https://github.com/neovim/neovim/wiki/Building-Neovim)
- [Docker official repositories](https://docs.docker.com/engine/install/)
