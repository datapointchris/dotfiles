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
shell/build/diagnostic essentials are `core`. `Subscription.wants` in
`src/dotfiles/machine.py` does the filtering, so there is still one list, not two. See
[Minimal Manifest for Servers](../learnings/minimal-manifest-for-servers.md).

## Shell Plugins (Git Clone)

**When to use**: ZSH plugins that need to be sourced directly

**Installation target**: `~/.config/zsh/plugins/`

**Method**: Git clone from upstream repositories

**Plugins**: the `shell_plugins` section of `install/packages.yml` is the list, each entry carrying
its own description. Read it with `dotfiles packages list --source shell_plugins` rather than
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
- Update: `dotfiles plugins apply`

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

**Go, cargo, release and custom-installer entries carry currency; npm and uv do not.** That is not
an inconsistency to even up. `go install @latest` and `cargo binstall` *are* the upgrade and
nothing else moves them, so being behind the repo the declaration names is drift `plan` reports.
npm and PyPI decide what latest means and upgrade in bulk, so asking per package is asking their
own question back.

**A GUI declares `reports_version: false` and is not currency-checked.** The probe runs whatever
binary the declaration names, and `webviewrs` takes its first argument as a URL: it opened a window
titled `version` and blocked three `dotfiles plan` runs on its event loop. Do not fix that by
dropping the bare `version` probe, which is the read `terrascan` needs.

## Implementation

### Single Source of Truth: packages.yml

All package versions, repositories, and configurations are centralized in `install/packages.yml`. This repo previously maintained both a Brewfile and packages.yml, which guaranteed drift — the migration found ~70 duplicate packages and tools that existed in one list but not the other. Lesson: if two lists describe the same things, one of them is wrong.

**Every installation type is catalogued in packages.yml, including custom installers.** There is no auto-detection anywhere: `install.sh`, `dotfiles apply` and `src/dotfiles/create_bundle.py` all drive from the corresponding packages.yml section rather than listing directories. A script with no catalog entry (or a catalog entry with no script) is a hard error — see [Drift Detection](#drift-detection) below.

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
honoured for `github_releases` today. **The catalog rejects a constraint declared in a section
that does not yet honour one** — that rule is the whole design, because the failure it prevents
already happened: four version fields sat in this file unread, one of them eight versions stale.

### Drift Detection

`dotfiles machines check` enforces that `packages.yml`, the machine manifests, and what can install
them stay in sync. It runs on every commit via pre-commit, and `src/dotfiles/validate.py` is where it
lives.

**Most of what it once checked, it no longer performs itself.** Every per-entry rule — required
fields, unknown keys, duplicate names, declared types, the version constraints — is the section's
dataclass in `catalog.py`, and a manifest naming a retired runtime gate is `machine.RETIRED_KEYS`.
Validation loads both files through the typed loaders and reports what they refuse, so the shape a
reader consumes and the shape the gate enforces cannot disagree. It used to re-parse the same YAML
as raw dictionaries, with its own idea of how a section is spelled and its own copy of the retired
keys, and nothing kept the two copies in step.

What is left is the three questions no single file can answer about itself, because each is a
relationship between two of them:

- **A manifest naming an entry that does not exist** — the no-op that shipped `todoui` and `forge`
  ghost-installed for weeks. The resolver cannot catch it: subscription is a membership test, so a
  name matching nothing is silently dropped rather than refused.
- **An entry nothing can install** — a `github_releases` or `custom_installers` entry with no
  function in `src/dotfiles/providers/`. Both were a directory of one script per entry, and the
  check followed them into Python: the guarantee was never "a file exists with this name", it was
  "something knows how to install this".
- **An entry no manifest names** — a warning rather than an error, because an entry lands in
  `packages.yml` before the manifest that wants it, and a tool being staged is not a broken
  declaration.

A catalog that will not load short-circuits the rest, for the same reason the machine walk puts this
row first: everything downstream is measured *against* the catalog, so findings derived from a file
nobody could parse would describe a declaration that does not exist.

The findings are values rather than printed lines, which is what lets one function serve the command,
the `machines` row of `dotfiles check`, and `apply`'s refusal to run against a declaration that will
not hold together. Tests are `tests/resolver/test_validate.py`, in-process against synthetic trees.

**`dotfiles plan` is the machine-side counterpart** and is deliberately a separate command. This one
compares the repo against itself and runs on every commit; `plan` compares *this machine* against what
its manifest declares, and a box part-way through a rollout is not a repo defect that should fail a
commit. `dotfiles check` asks the third question — whether anything is actually wrong — and a machine
merely behind on versions answers no.

What counts as evidence is the provider's own, declared on its class in `src/dotfiles/registry.py` and implemented in `src/dotfiles/evidence.py`: a binary on PATH for a release or a go tool, the tool directory for a uv tool that ships no console script, an app bundle for a Mac App Store app, and the package manager's own inventory for anything apt, pacman, brew or flatpak installed — because a package name is not a binary name, and `p7zip-full` installs `7zz` while `build-essential` installs no executable at all. A runtime is the one measured by asking it: a `go` on PATH that will not report a version is not an installed toolchain.

The declaration carries `command` where the binary name differs from the entry name (`markdownlint-cli` → `markdownlint`, `awscli` → `aws`) and `installed_path` for entries that install no binary (`bashselfupdate` is a sourced library). Without those, an installed tool reads as missing forever — the failure mode that makes a checker get ignored.

### Installation Scripts

What is left in `install/common/` is `plugins/` — the editor and terminal plugin
installers — and `lib/`, the libraries those installers source.

Every tool section installs through a provider now. uv, rustup, the Go tarball and
fnm's default Node alias are `src/dotfiles/providers/toolchain.py`; `go install`,
`cargo binstall`, `npm install -g` and `uv tool install` are `gotool.py`,
`cargo.py`, `npm.py` and `uvtool.py` beside it. Two of those carry a precondition
the section needs and the runtime does not — cargo-binstall, and npm's prefix —
which is the reason a provider is a module rather than one line in the registry.

The single source of truth for which tool is in which section is
`install/packages.yml`; its header comment maps each section to its install
method.

**Core Library** (`install/common/lib/`): what the bash that is left still shares.
Its README says why each file exists and what went with the installers that no
longer need it.

No section installs through a script. Every one of them is a provider under
`src/dotfiles/providers/`, where one verb converges and there is no second mode to
select. See `docs/architecture/github-releases.md` and
`docs/architecture/custom-installers.md`.

### Main Installation Flow

`install.sh` is a POSIX bootstrap whose only job is reaching the CLI: check `git` and `tar`, stage a bundle, install uv, install this package, then print the `dotfiles apply` that installs the machine. What that apply does is the whole plan, sorted by `resolve.Stage`, and the order is a dependency chain rather than a listing — symlinks land after the tools that provide `task` and before tpm reads the tmux config it deploys, and system configuration is last because every row of it needs the package it configures to be installed first.

### Taskfile Tasks

The `Taskfile.yml` provides convenience tasks for common operations but delegates complex logic to shell scripts:

`task --list-all` from inside the repo is the roster; see
[Task Reference](../reference/tools/tasks.md) for how the file is organised.

## Maintenance

**Updating tools**:

```bash
# Converge one section — Rust tools, Go tools, GitHub releases, custom installers
dotfiles packages apply --source cargo_packages

# System packages
sudo apt update && sudo apt upgrade
```

**Version checking**: Each install script checks current version before installing, skipping if acceptable version already present.

## Related Documents

- [Shell Libraries](shell-libraries.md) - The libraries installers source
- [App Installation Patterns](../learnings/app-installation-patterns.md) - Go apps vs shell scripts
- [Resilient Installation Patterns](../learnings/resilient-installation-patterns.md) - Failure isolation and re-runnability
