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

- Install: `dotfiles plugins apply` — the clone is `src/dotfiles/resources/plugins.py`
- Update: `dotfiles update plugins`

## Installation Location Strategy

Every install method writes to its own directory, and PATH order decides which
copy wins. The principle is that user-installed tools outrank system ones, and
each ecosystem keeps its own prefix.

**PATH is built in two places, and they are not the same order.** `.zshenv` sets
a base that every shell gets, including non-interactive ones:

```bash
PATH="$HOME/.local/share/fnm/aliases/default/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:/usr/local/bin:$PATH"
```

Interactive shells then run `.zshrc`, which rebuilds the front of PATH with
`add_path`. **`add_path` prepends, so the last call wins** — the list there is
written deliberately backwards, system directories first and user ones last. Add
a new entry at the wrong end and it will be shadowed by everything below it.

Read the current answer rather than a copy of it:

```sh
echo $PATH | tr ':' '\n'
```

**The `bat`/`batcat` split is a naming problem, not a version one.** Ubuntu's
apt package installs the binary as `batcat`, and `fd` as `fdfind`, because both
names collide with existing Debian packages. Nothing that calls `bat` finds it,
so config and scripts would need per-platform branching. Installing both through
`cargo binstall` sidesteps it entirely — one name on every platform, which is
why they are `cargo_packages` and not `system_packages`.

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

**Every installation type is catalogued in packages.yml, including custom installers.** There is no auto-detection anywhere: `install.sh`, `update.sh`, and `src/dotfiles/create_bundle.py` all drive from the corresponding packages.yml section rather than listing directories. A script with no catalog entry (or a catalog entry with no script) is a hard error — see [Drift Detection](#drift-detection) below.

Read the file for the entries; the header comment on each section states what its fields mean. What
is worth stating here is the part that is not obvious from any single entry.

### Version constraints

**Latest is the default.** An entry that declares no constraint installs whatever upstream calls
newest, and almost every entry declares none.

Three optional keys express the exceptions, valid in principle on any entry:

| key | means |
| --- | --- |
| `version` | install exactly this |
| `min_version` | a resolved version below this is a problem, not drift |
| `max_version` | resolve to the newest release at or below this |

`version` is exclusive with the other two — a pin already answers both bounds, and accepting all
three describes a window nobody can predict. Values are **bare versions, never tags and never
operators**: `0.56.0`, not `v0.56.0`, `cli/v0.9.0` or `>=0.56.0`. The same release is spelled three
different ways across this catalog, so resolving a version to a tag is the resolver's job, not the
declaration's.

Enforcement arrives per section, because pinning means a different mechanism in each
(`cargo install --version`, `go install pkg@v1.2.3`, `uv tool install pkg==1.2.3`). Exact pins are
honoured for `github_releases` today. **`packages verify` rejects a constraint declared in a section
that does not yet honour one** — that rule is the whole design, because the failure it prevents
already happened: four version fields sat in this file unread, one of them eight versions stale.

### Drift Detection

The `packages verify` subcommand (in `src/dotfiles/catalog.py`) enforces that packages.yml, the machine manifests, and the installer script directories stay in sync. It runs on every commit via pre-commit and surfaces four classes of drift:

- **Shape errors** — an entry missing required fields (e.g., a `github_releases` entry with no `repo`), or duplicate names within a section.
- **Unresolved manifest names** — a manifest lists a name that has no corresponding packages.yml entry (the no-op that shipped `todoui` and `forge` ghost-installed for weeks).
- **Uninstallable entries** — a `github_releases` or `custom_installers` entry with no installer function in `src/dotfiles/providers/`. Both sections were a directory of one script per entry, and the check followed them into Python: the guarantee was never "a file exists with this name", it was "something knows how to install this".
- **Deprecated manifest keys** — `go: true` / `rust: true` / `nvm: true` / `uv: true` / `tenv: true`; these runtime gates were removed in Phase 1.6 in favor of name-list derivation.

A fifth, softer check warns when packages.yml defines an entry that no manifest subscribes to — useful for spotting orphans without failing the commit.

Behavior is authoritative in `--help` and `packages verify --help`. Tests live in `tests/apps/test_packages_verify.py` and drive verify against synthetic fixture trees (one test per check), so coverage doesn't depend on the real repo being in any particular state.

**`dotfiles check` is the machine-side counterpart** and is deliberately a separate command. `verify` compares the repo against itself and runs on every commit; `check` compares *this machine* against what its manifest declares, and a box part-way through a rollout is not a repo defect that should fail a commit.

What counts as evidence is per provider, in `src/dotfiles/resources/packages.py`: a binary on PATH for a release or a go tool, the tool directory for a uv tool that ships no console script, an app bundle for a Mac App Store app, and the package manager's own inventory for anything apt, pacman, brew or flatpak installed — because a package name is not a binary name, and `p7zip-full` installs `7zz` while `build-essential` installs no executable at all.

The registry carries `command` where the binary name differs from the entry name (`markdownlint-cli` → `markdownlint`, `awscli` → `aws`) and `installed_path` for entries that install no binary (`bashselfupdate` is a sourced library). Without those, an installed tool reads as missing forever — the failure mode that makes a checker get ignored.

### Installation Scripts

Located in `install/common/`:

**Directory Structure**:

- `language-managers/` - Language runtime / version-manager bootstrappers (uv, rustup, go)
- `language-tools/` - Per-language package installers, driven by the tool lists in `packages.yml`
- `plugins/` - Editor and terminal plugin installers

The specific tools in each category are defined in `install/packages.yml` (the single
source of truth) — this list describes what each directory is *for*, not its contents.

**Core Library** (`install/common/lib/`):

- `failure-logging.sh` - Structured failure reporting

The scripts that remain support `--update` for the update system and use structured error reporting. The `github_releases` and `custom_installers` sections do not: they are `src/dotfiles/providers/`, where one verb converges and there is no second mode to select. See `docs/architecture/github-releases.md` and `docs/architecture/custom-installers.md`.

### Main Installation Flow

`install.sh` is a POSIX bootstrap whose only job is reaching the CLI: check `git` and `tar`, stage a bundle, install uv, install this package, `exec dotfiles apply`. The phases and their order are `apply.REGISTRY` in `src/dotfiles/apply.py`, and the order is a dependency chain rather than a listing — symlinks land after the tools that provide `task` and before tpm reads the tmux config it deploys, and system configuration is last because every row of it needs the package it configures to be installed first.

### Taskfile Tasks

The `Taskfile.yml` provides convenience tasks for common operations but delegates complex logic to shell scripts:

`task --list-all` from inside the repo is the roster; see
[Task Reference](../reference/tools/tasks.md) for how the file is organised.

## Maintenance

**Updating tools**:

```bash
# Rust tools
cargo binstall -y <package>

# GitHub release tools — converge them all, or narrow to one section
dotfiles packages apply --source github_releases

# System packages
sudo apt update && sudo apt upgrade
```

**Version checking**: Each install script checks current version before installing, skipping if acceptable version already present.

## Related Documents

- [Shell Libraries](shell-libraries.md) - The libraries installers source
- [App Installation Patterns](../learnings/app-installation-patterns.md) - Go apps vs shell scripts
- [Resilient Installation Patterns](../learnings/resilient-installation-patterns.md) - Failure isolation and re-runnability
