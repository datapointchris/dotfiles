# Package Management Architecture

**Purpose**: Unified strategy for installing and managing CLI tools across all platforms

## Philosophy

**Priority**: Latest versions and cross-platform consistency over system package manager convenience

**Rationale**: Ubuntu LTS (and other system package managers) ship conservative versions that are often 6-12 months (or more) behind upstream. This causes:

- Missing features and bug fixes
- Plugin compatibility issues (especially Neovim)
- Naming conflicts (bat/batcat, fd/fdfind)
- Platform-specific workarounds

By using universal installation methods (cargo-binstall, GitHub releases), we get:

- ✅ Same versions on macOS and Linux
- ✅ Latest features and fixes
- ✅ Consistent binary names
- ✅ User-space installation (no sudo needed except for Go)

## Three-Tier Strategy

### Tier 1: GitHub Releases (Latest Stable)

**When to use**: Core tools requiring specific versions, not available in cargo/language ecosystems

**Installation target**: `~/.local/bin` or `~/.local/{tool-name}/`

**Method**: Download pre-built binaries from GitHub releases

**Tools**:

- `yq` - YAML processor (single binary)
- `go` - Build toolchain (extract to `/usr/local/go` per official docs)
- `fzf` - Fuzzy finder (build from source with Go)
- `neovim` - Editor (extract to `~/.local/nvim-linux-x86_64/`, symlink binary)
- `lazygit` - Git TUI (single binary)
- `yazi` - File manager (single binary + plugins)
- `glow` - Markdown renderer (single binary)
- `duf` - Disk usage utility (single binary)
- `awscli` - AWS command line tool (platform-specific installer)

**Advantages**:

- Latest stable releases
- No compilation required (except fzf)
- Universal across platforms
- Predictable versions

### Tier 2: cargo-binstall (Rust Ecosystem)

**When to use**: Rust CLI tools where we want latest versions

**Installation target**: `~/.cargo/bin`

**Method**: Download pre-compiled Rust binaries (much faster than `cargo install`)

**Tools**:

- `bat` - cat alternative (no "batcat" naming issue!)
- `fd` - find alternative (no "fdfind" naming issue!)
- `zoxide` - cd alternative
- `eza` - ls alternative
- `git-delta` - Git diff viewer
- `tinty` - Theme manager
- `cargo-update` - Keep cargo tools updated

**Advantages**:

- Pre-compiled binaries (fast, 10-30 seconds)
- Latest versions from crates.io
- No naming conflicts
- Consistent across platforms

**vs cargo install**:

- `cargo install` compiles from source (5-10 minutes per tool)
- `cargo-binstall` downloads pre-built binaries (10-30 seconds)
- Same result, 20x faster!

### Tier 3: System Package Managers (Stable)

**When to use**: System utilities where version doesn't matter, or tools with large system dependencies

**Installation target**: `/usr/bin` (lowest PATH priority)

**Method**: apt (Ubuntu), brew (macOS), pacman (Arch)

**Tools**:

**Shell**:

- `zsh` - Shell itself
- `tmux` - Version 3.4 is acceptable (3.5a is only bugfixes)

**System utilities**:

- `ripgrep` - Currently up-to-date in apt (14.1.0)
- `tree`, `htop`, `jq` - Stable tools, version doesn't matter

**Build tools**:

- `build-essential`, `curl`, `wget`, `unzip`
- `pkg-config`, `libssl-dev`, `ca-certificates`

**Multimedia** (large dependencies):

- `ffmpeg` - Video/audio processing
- `imagemagick` - Image manipulation
- `poppler-utils` - PDF tools
- `chafa` - Image preview
- `7zip` - Archive extraction

**Advantages**:

- Fast installation (pre-compiled, cached)
- System integration (man pages, completions)
- Security updates via `apt upgrade`
- Shared dependencies

**Disadvantages**:

- Outdated versions (6-12+ months behind)
- Naming conflicts on Ubuntu (batcat, fdfind)

## Shell Plugins (Git Clone)

**When to use**: ZSH plugins that need to be sourced directly

**Installation target**: `~/.config/zsh/plugins/`

**Method**: Git clone from upstream repositories

**Plugins** (defined in `management/packages.yml`):

- `git-open` - Open repo in browser from terminal
- `zsh-vi-mode` - Better vi-mode for ZSH
- `forgit` - Interactive git commands with fzf
- `zsh-syntax-highlighting` - Fish-like syntax highlighting for ZSH

**Advantages**:

- Latest versions from upstream
- Easy to update with `git pull`
- Consistent across all platforms
- No package manager dependencies

**Management**:

- Install: `task shell:install` (reads from packages.yml)
- Update: `task shell:update` or `task update-all`

## Installation Location Strategy

```text
PATH Priority (highest to lowest):

~/.cargo/bin/          # Tier 2: Rust tools (bat, fd, eza, zoxide, delta, tinty)
~/.local/bin/          # Tier 1: GitHub releases (nvim, lazygit, fzf, yq, yazi)
~/go/bin/              # Go-installed binaries (sess, toolbox)
/usr/local/go/bin/     # Go toolchain
~/.local/share/npm/bin # npm global packages
/usr/local/bin/        # Homebrew/system-wide installs
/usr/bin/              # System packages (lowest priority)
```

**Why this order?**

1. **User tools override system** - Your latest tools take precedence
2. **Language ecosystems together** - Each package manager in its own directory
3. **System packages last** - Stable but outdated, lowest priority

See [PATH Ordering Strategy](path-ordering-strategy.md) for complete details.

## Special Case: Neovim Directory Structure

**Why neovim can't be a single binary like lazygit:**

Neovim is not a self-contained binary - it's an application bundle with many support files:

```text
~/.local/nvim-linux-x86_64/
├── bin/
│   └── nvim              # The executable
├── lib/
│   └── nvim/             # Shared libraries
└── share/
    ├── nvim/
    │   └── runtime/      # CRITICAL: syntax files, plugins, help docs
    ├── man/              # Man pages
    └── locale/           # Translations
```

**The Problem**: The `nvim` binary expects runtime files at `../share/nvim/runtime/` (relative to the binary location).

**What happens if we move just the binary**:

```bash
# DON'T DO THIS:
mv nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim

# Neovim will look for runtime at:
~/.local/share/nvim/runtime/  # Wrong location!

# Actual location:
~/.local/nvim-linux-x86_64/share/nvim/runtime/  # Correct location

# Result: Neovim fails with "runtime files not found"
```

**The Solution**: Keep directory structure intact, symlink the binary:

```bash
# Extract full structure (neovim changed filename from nvim-linux64 to nvim-linux-x86_64)
tar -C ~/.local -xzf nvim-linux-x86_64.tar.gz
# Creates: ~/.local/nvim-linux-x86_64/

# Symlink binary into PATH
ln -sf ~/.local/nvim-linux-x86_64/bin/nvim ~/.local/bin/nvim

# Now:
# - Binary is in PATH (via ~/.local/bin/nvim)
# - Binary finds runtime (../share/nvim/runtime/ from real location)
# - Everything works perfectly!
```

**Compare to lazygit** (single binary):

```bash
# lazygit is self-contained:
tar -xzf lazygit.tar.gz lazygit
mv lazygit ~/.local/bin/lazygit  # Direct move works!

# Everything it needs is compiled into the single binary
```

**Summary**:

- **Single binary tools** (lazygit, yq, fzf) → Direct to `~/.local/bin/`
- **Application bundles** (neovim) → Extract to `~/.local/{tool-name}/`, symlink binary

## Version Comparison

See [Package Version Analysis](../learnings/package-version-analysis.md) for detailed version comparisons.

**Highlights**:

| Tool | Ubuntu 24.04 apt | Latest | Installation Method |
|------|-----------------|--------|---------------------|
| fzf | 0.44.1 | 0.66.1 | Build from source (22 versions ahead!) |
| neovim | 0.9.5 | 0.11+ | GitHub releases (major version ahead) |
| go | 1.22 | 1.23+ | GitHub releases (official method) |
| bat | 0.24.0 | 0.26.0 | cargo-binstall |
| fd | 9.0.0 | 10.2.0 | cargo-binstall |
| zoxide | 0.8.x | 0.9.6 | cargo-binstall |
| tmux | 3.4 | 3.5a | apt (acceptable, only bugfixes) |
| ripgrep | 14.1.0 | 14.1.0 | apt (current!) |

## Implementation

### Single Source of Truth: packages.yml

All package versions, repositories, and configurations are centralized in `management/packages.yml`:

```yaml
runtimes:
  go:
    min_version: "1.23"
  node:
    version: "24.11.0"
  python:
    min_version: "3.12"

github_binaries:
  - name: neovim
    repo: neovim/neovim
    version: "0.11.0"
  - name: lazygit
    repo: jesseduffield/lazygit
    version: "0.44.1"
  # ... more tools

cargo_packages:
  - bat
  - fd-find
  - eza
  - zoxide
  - git-delta
  - tinty
  - cargo-update

uv_tools:
  - name: ruff
    package: ruff
  # ... more tools
```

All installation scripts and taskfiles read from this single source. Change a version once, and it applies everywhere.

### Installation Scripts

Located in `management/scripts/`:

**Core Helpers**:

- `install-install-helpers.sh` - Shared functions for GitHub binary installation, version checking, manual install instructions

**GitHub Release Tools**:

- `install-go.sh` - Latest Go from go.dev
- `install-fzf.sh` - Build fzf from source with Go
- `install-neovim.sh` - Extract neovim bundle, symlink binary
- `install-lazygit.sh` - Download single binary
- `install-yazi.sh` - Download binaries, install plugins
- `install-glow.sh` - Markdown renderer
- `install-duf.sh` - Disk usage utility
- `install-awscli.sh` - AWS CLI v2 (platform-specific)

**Language Ecosystems**:

- `install-rust.sh` - Install Rust via rustup
- `install-uv.sh` - Install uv for Python management
- `install-cargo-binstall.sh` - Bootstrap cargo-binstall
- `install-cargo-tools.sh` - Install all cargo packages from packages.yml
- `npm-install-globals.sh` - Install npm global packages from packages.yml

**Plugins**:

- `install-tmux-plugins.sh` - Install tmux plugins

All GitHub release scripts use `install-install-helpers.sh` for consistent error handling, version checking, and graceful firewall failure recovery with manual installation instructions.

### Taskfile Organization

Platform taskfiles (`wsl.yml`, `macos.yml`, `arch.yml`) and specialized taskfiles define installation tasks:

**Main Installation Tasks**:

```yaml
install-go:          # GitHub releases → /usr/local/go
install-fzf:         # Build from source → ~/.local/bin
install-neovim:      # GitHub releases → ~/.local/bin (symlink)
install-lazygit:     # GitHub releases → ~/.local/bin
install-yazi:        # GitHub releases → ~/.local/bin
install-glow:        # GitHub releases → ~/.local/bin
install-duf:         # GitHub releases → ~/.local/bin
install-awscli:      # AWS official installer

install-cargo-binstall:  # Bootstrap for Rust tools
install-cargo-tools:     # Reads package list from packages.yml
```

**Specialized Taskfiles** (`management/taskfiles/`):

- `go-tools.yml` - Go CLI tools installed via `go install` (cheat, etc.)
- `brew.yml` - Homebrew package management (macOS)
- `mas.yml` - Mac App Store applications (macOS)
- Platform-specific taskfiles for each supported OS

### Main Installation Flow

`Taskfile.yml` orchestrates 9 phases:

1. System packages (apt)
2. GitHub release tools
3. Rust/cargo tools
4. Language package managers
5. Shell configuration
6. Custom Go applications
7. Symlink dotfiles
8. Theme system
9. Plugin installation

### Task Separation Pattern

Each platform's package installation uses a two-task pattern:

```yaml
install-packages (public):
  - Pre-setup (apt update, pacman -Sy, etc.)
  - task: install-system-packages
  - Post-setup (docker-compose, fix-library-links, etc.)

install-system-packages (internal):
  - Bootstrap PyYAML
  - Parse packages.yml
  - Install packages
```

Platform-specific setup (pre/post) is isolated in `install-packages`, while core installation logic remains identical across platforms in `install-system-packages`.

See: `management/taskfiles/{macos,wsl,arch}.yml`

## Maintenance

**Updating tools**:

```bash
# Rust tools
cargo install-update -a

# Manually check GitHub releases
task wsl:install-go        # Updates if new version available
task wsl:install-neovim    # Updates if new version available
task wsl:install-lazygit   # Updates if new version available

# System packages
sudo apt update && sudo apt upgrade
```

**Version checking**: Each install script checks current version before installing, skipping if acceptable version already present.

## Related Documents

- [PATH Ordering Strategy](path-ordering-strategy.md) - How tool resolution works
- [Package Version Analysis](../learnings/package-version-analysis.md) - Detailed version comparisons
- [App Installation Patterns](../learnings/app-installation-patterns.md) - Go apps vs shell scripts
- [Idempotent Installation Patterns](../learnings/idempotent-installation-patterns.md) - Re-runnable scripts
