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
- ✅ User-space installation (no sudo needed)

## Three-Tier Strategy

### Tier 1: GitHub Releases (Latest Stable)

**Installation target**: `~/.local/bin` or `~/.local/{tool-name}/`

**Method**: Download pre-built binaries from GitHub releases

**Tools**: `packages list --section=github_releases`

**When to use**: default to a system package and move a tool here only for a
reason. The reasons that hold up:

- Releases come faster than the package managers ship them. "Frequent" means the
  tool is actively evolving, not just patching.
- It is security tooling, where a stale version has real consequences — `trivy`
  releases monthly and a lagging vulnerability database means missed CVEs, which
  is the strongest case in the list.
- The binary is self-contained, so nothing is gained from the distro's
  dependency handling.
- The same version is wanted on macOS and Linux at once.

The inverse test names the tool that should *not* be here: `mkcert` last
released in 2022, ships as 1.4.4 in every package manager, and is
feature-complete. A GitHub-release installer for it would be a hand-maintained
version pin replacing something the OS updates for free.

**Advantages**:

- Latest stable releases
- No compilation required
- Universal across platforms
- Predictable versions

### Tier 2: cargo-binstall (Rust Ecosystem)

**When to use**: Rust CLI tools where we want latest versions

**Installation target**: `~/.cargo/bin`

**Method**: Download pre-compiled Rust binaries (much faster than `cargo install`). Packages with a `repo` field in packages.yml are compiled from source via `cargo install --git` instead — used for personal Rust tools not published to crates.io.

**Tools**:

See `install/packages.yml` (`cargo_packages` section) for the current list.

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

**Shell & Terminal**:

- `zsh` - Shell itself
- `tmux` - Version 3.4 is acceptable (3.5a is only bugfixes)

**System utilities**:

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

#### Core vs workstation split

System packages carry a second, orthogonal tier that controls *which machines*
install them (distinct from the Tier 1/2/3 installation-method split above).
Each entry in the single `system_packages` list may be tagged `tier: core`;
untagged entries default to workstation-only. A manifest declares which set it
wants via `system_packages: core | workstation` — a workstation installs
everything, a minimal server (the `linux-lxc-server` manifest) installs only the
core base. The multimedia and docker packages above are workstation-only; the
shell/build/diagnostic essentials are `core`. `parse_packages.py --tier` does the
filtering, so there is still one list, not two. See
[Minimal Manifest for Servers](../learnings/minimal-manifest-for-servers.md).

## Shell Plugins (Git Clone)

**When to use**: ZSH plugins that need to be sourced directly

**Installation target**: `~/.config/zsh/plugins/`

**Method**: Git clone from upstream repositories

**Plugins**: the `shell_plugins` section of `install/packages.yml` is the list, each entry carrying
its own description. Read it with `parse_packages --type=shell-plugins --format=names` rather than
copying the names here, where they only go stale.

Load order is not arbitrary and lives in `.zshrc`, not in the manifest: `zsh-syntax-highlighting`
must be sourced last so it can wrap every widget the other plugins define, and `zsh-vi-mode`
overwrites the whole keymap when it initializes, which is why every other keybinding is re-applied
from `zvm_after_init`.

**Advantages**:

- Latest versions from upstream
- Easy to update with `git pull`
- Consistent across all platforms
- No package manager dependencies

**Management**:

- Install: `install/common/plugins/shell-plugins.sh` (reads from packages.yml)
- Update: `dotfiles update plugins`

## Installation Location Strategy

```text
PATH Priority (highest to lowest):

~/.cargo/bin/          # Tier 2: Rust tools (bat, fd, eza, zoxide, delta)
~/.local/bin/          # Tier 1: GitHub releases (nvim, lazygit, fzf, yq, yazi)
~/go/bin/              # Go-installed binaries (toolbox, sesh)
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

The install method chosen for each tool is declared in `install/packages.yml` — that file is the
source of truth, not a list here. The rule behind the choices: a distro package that trails
upstream by a major version goes to GitHub releases or `cargo-binstall` instead.

## Implementation

### Single Source of Truth: packages.yml

All package versions, repositories, and configurations are centralized in `install/packages.yml`. This repo previously maintained both a Brewfile and packages.yml, which guaranteed drift — the migration found ~70 duplicate packages and tools that existed in one list but not the other. Lesson: if two lists describe the same things, one of them is wrong.

**Every installation type is catalogued in packages.yml, including custom installers.** There is no auto-detection anywhere: `install.sh`, `update.sh`, and `install/offline/create-bundle.sh` all drive from the corresponding packages.yml section rather than listing directories. A script with no catalog entry (or a catalog entry with no script) is a hard error — see [Drift Detection](#drift-detection) below.

Package definitions in packages.yml:

```yaml
runtimes:
  go:
    min_version: "1.23"
  node:
    version: "24.11.0"
  python:
    min_version: "3.12"

github_releases:
  - name: neovim
    repo: neovim/neovim
    version: "0.11.0"
  - name: lazygit
    repo: jesseduffield/lazygit
    version: "0.44.1"
  # ... more tools

cargo_packages:
  - name: bat
    command: bat
    description: cat with syntax highlighting
  - name: fd-find
    command: fd
    description: modern find replacement
  # ... more tools (bat, eza, zoxide, git-delta, oxker, broot)

uv_tools:
  - name: ruff
    package: ruff
  # ... more tools
```

All installation scripts read from this single source. Change a version once, and it applies everywhere.

### Drift Detection

The `packages verify` subcommand (in `apps/common/packages`) enforces that packages.yml, the machine manifests, and the installer script directories stay in sync. It runs on every commit via pre-commit and surfaces four classes of drift:

- **Shape errors** — an entry missing required fields (e.g., a `github_releases` entry with no `repo`), or duplicate names within a section.
- **Unresolved manifest names** — a manifest lists a name that has no corresponding packages.yml entry (the no-op that shipped `todoui` and `forge` ghost-installed for weeks).
- **Script parity breaks** — a script in `install/common/github-releases/` or `install/common/custom-installers/` with no packages.yml entry, or vice versa.
- **Deprecated manifest keys** — `go: true` / `rust: true` / `nvm: true` / `uv: true` / `tenv: true`; these runtime gates were removed in Phase 1.6 in favor of name-list derivation.

A fifth, softer check warns when packages.yml defines an entry that no manifest subscribes to — useful for spotting orphans without failing the commit.

Behavior is authoritative in `--help` and `apps/common/packages verify --help`. Tests live in `tests/apps/test_packages_verify.py` and drive verify against synthetic fixture trees (one test per check), so coverage doesn't depend on the real repo being in any particular state.

**`packages missing` is the machine-side counterpart** and is deliberately a separate command. `verify` compares the repo against itself and runs on every commit; `missing` compares *this machine* against what its manifest declares, and a box part-way through a rollout is not a repo defect that should fail a commit. It is what `dotfiles doctor` calls, and what `dotfiles update` leans on when it reports the tools it declined to install.

Both rely on `check_installed` resolving an entry to something observable, which is why the registry carries `command` where the binary name differs from the entry name (`markdownlint-cli` → `markdownlint`, `awscli` → `aws`) and `installed_path` for entries that install no binary at all (`bashselfupdate` is a sourced library). Without those, an installed tool reads as missing forever — the failure mode that makes a checker get ignored.

### Installation Scripts

Located in `install/common/`:

**Directory Structure**:

- `github-releases/` - Installers for tools shipped as prebuilt GitHub release binaries
- `language-managers/` - Language runtime / version-manager bootstrappers (uv, rustup, go)
- `language-tools/` - Per-language package installers, driven by the tool lists in `packages.yml`
- `custom-installers/` - Vendor-specific installers that don't fit the other patterns
- `plugins/` - Editor and terminal plugin installers

The specific tools in each category are defined in `install/packages.yml` (the single
source of truth) — this list describes what each directory is *for*, not its contents.

**Core Library** (`install/common/lib/`):

- `failure-logging.sh` - Structured failure reporting
- `github-release-installer.sh` - Shared functions for GitHub release tools

All installer scripts support `--update` for the update system and use structured error reporting.

The root `install.sh` orchestrates the installation process, detecting the platform and running appropriate scripts from `install/{platform}/` and `install/common/{category}/`.

### Main Installation Flow

`install.sh` orchestrates installation phases:

1. System packages (brew/apt/pacman)
2. GitHub release tools
3. Rust/cargo tools
4. Language package managers
5. Shell configuration
6. Custom Go applications
7. Symlink dotfiles
8. Theme system
9. Plugin installation

### Taskfile Tasks

The `Taskfile.yml` provides convenience tasks for common operations but delegates complex logic to shell scripts:

```yaml
symlinks:link        # Deploy symlinks
symlinks:check       # Verify symlinks
docs:serve           # Local docs server
```

See [Task Reference](../reference/tools/tasks.md) for all available tasks.

## Maintenance

**Updating tools**:

```bash
# Rust tools
cargo binstall -y <package>

# GitHub release tools — re-run installer script directly
bash install/common/github-releases/neovim.sh
bash install/common/github-releases/lazygit.sh

# System packages
sudo apt update && sudo apt upgrade
```

**Version checking**: Each install script checks current version before installing, skipping if acceptable version already present.

## Related Documents

- [PATH Ordering Strategy](path-ordering-strategy.md) - How tool resolution works
- [App Installation Patterns](../learnings/app-installation-patterns.md) - Go apps vs shell scripts
- [Resilient Installation Patterns](../learnings/resilient-installation-patterns.md) - Failure isolation and re-runnability
