# Package Management Architecture

**Purpose**: Unified strategy for installing and managing CLI tools across all platforms

## Latest versions and one binary name beat package-manager convenience

Ubuntu LTS and its peers ship conservative versions, often 6-12 months behind
upstream. Neovim plugins are the first thing that breaks against a stale editor.
Ubuntu also renames binaries that collide with existing Debian packages, so `bat`
arrives as `batcat` and `fd` as `fdfind`. Cargo-binstall and GitHub releases put
one version and one name on macOS and Linux, in user space, with no sudo.

## Three install tiers, ordered by how much the version matters

### Tier 1: GitHub Releases (Latest Stable)

Pre-built binaries, into `~/.local/bin` or `~/.local/<tool-name>/`. Read the
roster with `packages list --section=github_releases`.

Default to a system package. Move a tool here only for a reason. The reasons
that hold up:

- Releases come faster than the package managers ship them. "Frequent" means the
  tool is actively evolving, not just patching.
- It is security tooling. `trivy` releases monthly, and a lagging vulnerability
  database means missed CVEs. That is the strongest case in the list.
- The binary is self-contained, so the distro's dependency handling gains
  nothing.
- The same version is wanted on macOS and Linux at once.

The inverse test names the tool that should *not* be here. `mkcert` last
released in 2022, ships as 1.4.4 in every package manager, and is
feature-complete. A GitHub-release installer for it would be a hand-maintained
version pin replacing something the OS updates for free.

### Tier 2: cargo-binstall (Rust Ecosystem)

Rust CLI tools, into `~/.cargo/bin`. `cargo-binstall` downloads the release
binary the project already published, where `cargo install` compiles the same
code from source. That is the whole reason it is the default here.

An entry names its asset without asking the network, which is what lets these
tools go into an offline bundle. The fields that do it are `CargoPackage` in
`src/dotfiles/catalog.py`.

### Tier 3: System Package Managers (Stable)

apt, brew and pacman, into `/usr/bin` at the lowest PATH priority. Use them for
system utilities whose version does not matter, and for anything dragging large
multimedia or compiled dependencies behind it. Read the roster with
`packages list --section=system_packages`.

#### Core vs workstation split

System packages carry a second tier that controls *which machines* install them,
orthogonal to the Tier 1/2/3 installation-method split above. An entry may be
tagged `tier: core`, and untagged entries default to workstation-only. A manifest
declares which set it wants via `system_packages: core | workstation`. A
workstation installs everything; a minimal server installs only the core base.
`Subscription.wants` in `src/dotfiles/machine.py` does the filtering, so there is
still one list rather than two. See
[Minimal Manifest for Servers](../learnings/minimal-manifest-for-servers.md).

## Shell plugin load order lives in `.zshrc`, not in the manifest

ZSH plugins that need sourcing directly are git-cloned into
`~/.config/zsh/plugins/` by `src/dotfiles/resources/plugins.py`.

`zsh-syntax-highlighting` must be sourced last so it can wrap every widget the
other plugins define. `zsh-vi-mode` overwrites the whole keymap when it
initializes, which is why every other keybinding is re-applied from
`zvm_after_init`.

## Installation Location Strategy

Every install method writes to its own directory, and PATH order decides which
copy wins. User-installed tools outrank system ones, and each ecosystem keeps its
own prefix.

**A declared tool is measured in its own provider's directory, not by name on
PATH.** `evidence.in_provider_dir` is where that happens, and the two questions
come apart wherever another manager ships the same tool: a `cargo_packages` entry
answering from `/usr/local/bin` is a brew formula somebody installed, not a
declaration this repo has ever satisfied. Such an entry reads `missing` and the
row names the copy that does answer, so a machine whose `rg --version` works is
never reported as simply lacking it.

**PATH is built in two places, and they are not the same order.** `.zshenv` sets
a base every shell gets, including non-interactive ones. Interactive shells then
run `.zshrc`, which rebuilds the front of PATH with `add_path`. **`add_path`
prepends, so the last call wins** — the list there is written deliberately
backwards, system directories first and user ones last. Add a new entry at the
wrong end and everything below it shadows it.

Read the current answer rather than a copy of it:

```sh
echo $PATH | tr ':' '\n'
```

**The `bat`/`batcat` split is a naming problem, not a version one.** Nothing that
calls `bat` finds `batcat`, so config and scripts would need per-platform
branching. Installing both through `cargo binstall` sidesteps it entirely — one
name on every platform, which is why they are `cargo_packages` and not
`system_packages`.

## Neovim ships a bundle, so the tree is what gets installed

The `nvim` binary resolves its runtime files relative to its own location, at
`../share/nvim/runtime/`. Moving the binary alone into `~/.local/bin/` therefore
sends it looking in `~/.local/share/nvim/runtime/`, and it fails with "runtime
files not found". The whole extracted tree lands in `~/.local/nvim-linux-x86_64/`
and only the binary is symlinked onto PATH, which keeps the relative path intact.
`src/dotfiles/providers/releases.py` declares that with `tree=True`.

## Currency is asked only of the tools that can answer it

**Go, cargo, release and custom-installer entries carry currency; npm and uv do
not.** That is not an inconsistency to even up. `go install @latest` and
`cargo binstall` *are* the upgrade and nothing else moves them, so being behind
the repo the declaration names is drift `plan` reports. npm and PyPI decide what
latest means and upgrade in bulk, so asking per package is asking their own
question back.

An entry that cannot be asked declares so rather than being probed and hoped for.
Which clauses have to hold, and the GUI whose probe blocked three `dotfiles plan`
runs on its own event loop, are `_has_currency` in
`src/dotfiles/resources/packages.py`.

## Implementation

### Single Source of Truth: packages.yml

All package versions, repositories, and configurations are centralized in
`install/packages.yml`. This repo once maintained both a Brewfile and
packages.yml, which guaranteed drift — the migration found ~70 duplicate packages
and tools that existed in one list but not the other. Lesson: if two lists
describe the same things, one of them is wrong.

**Every installation type is catalogd, including custom installers.** There is
no auto-detection anywhere: `install.sh`, `dotfiles apply` and
`src/dotfiles/create_bundle.py` all drive from the corresponding packages.yml
section rather than listing directories. An entry nothing can install is a hard
error, and the reverse — an installer function nothing declares — is asserted by
`tests/install/`.

Read the file for the entries; the header comment on each section states what its
fields mean.

### Version constraints

**Latest is the default.** An entry that declares no constraint installs whatever
upstream calls newest, and almost every entry declares none.

Constraint values are **bare versions, never tags and never operators**: `0.56.0`,
not `v0.56.0`, `cli/v0.9.0` or `>=0.56.0`. The same release is spelled three
different ways across this catalog, so resolving a version to a tag is the
resolver's job rather than the declaration's.

The three constraint keys, and why a section whose provider honors none of them
refuses the key outright, are the `Entry` docstring in `src/dotfiles/catalog.py`.

### Drift Detection

`dotfiles machines check` asks whether `packages.yml`, the machine manifests and
what can install them still agree. It runs on every commit via pre-commit. Which
questions it asks, and why each is a relationship no single file can answer about
itself, are the module docstring in `src/dotfiles/validate.py`.

**`dotfiles plan` is the machine-side counterpart** and is deliberately a separate
command. This one compares the repo against itself and runs on every commit;
`plan` compares *this machine* against what its manifest declares, and a box
part-way through a rollout is not a repo defect that should fail a commit.
`dotfiles check` asks the third question — whether anything is actually wrong —
and a machine merely behind on versions answers no.

Evidence that a declared item is installed is the provider's own, in
`src/dotfiles/evidence.py`. Two fields on the declaration are the editor's job
there. Declare `command` where the binary name differs from the entry name
(`markdownlint-cli` → `markdownlint`, `awscli` → `aws`). Declare `installed_path`
for an entry that installs no binary — `bashselfupdate` is a sourced library.
Without those, an installed tool reads as missing forever, which is the failure
mode that makes a checker get ignored.

### Every section installs through a provider, never a script

`eza -1 src/dotfiles/providers/` is the roster, and `install/packages.yml`'s header
comment maps each section to its install method. A provider is a module rather
than one line in a registry because some carry a precondition the runtime does
not — cargo-binstall itself, and npm's prefix. See
[GitHub Releases](github-releases.md) and
[Custom Installers](custom-installers.md).

What is left in `install/common/lib/` is the bash that a human still runs by hand.
Its README says why each file is there, which is the part a reader cannot recover
from the code.

### Main Installation Flow

`install.sh` is a POSIX bootstrap whose only job is reaching the CLI. It stops
once the package is installed and prints the `dotfiles apply` that installs the
machine. What that apply does is the whole plan, sorted by `plan.Stage`, whose
order is a dependency chain rather than a listing.

## Related Documents

- [Shell Libraries](shell-libraries.md) - The libraries installers source
- [Task Reference](../reference/tools/tasks.md) - How the Taskfile is organized
- [App Installation Patterns](../learnings/app-installation-patterns.md) - Go apps vs shell scripts
- [Resilient Installation Patterns](../learnings/resilient-installation-patterns.md) - Failure isolation and re-runnability
