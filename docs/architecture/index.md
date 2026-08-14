---
icon: material/city
---

# Architecture

How the dotfiles repository is organized and why.

**External tools** (installed from GitHub, not in this repo):

- `toolbox`: Go app via `go install github.com/datapointchris/toolbox`
- `sesh`: Go app via `go install github.com/joshmedeski/sesh/v2`
- `theme`, `font`: Bash tools cloned to `~/.local/share/`

## Symlink System

A common base plus one `<axis>/<value>` directory per coordinate axis, across
three trees: `configs/` into `$HOME`, `apps/` into `~/.local/bin/`, `shell/` into
`~/.local/shell/`. Which of them a machine takes is decided by its coordinates
rather than by a platform string, so the Wayland tree lives once under
`display/wayland/` regardless of which Linux is underneath it, and the apt
helpers reach the Ubuntu work box as well as the LXC.

Driven through `dotfiles symlinks`, which works from any directory; `task` is equivalent
but only from inside the repo — see [Management Interface](management-interface.md).
The scheme, and why two variants may never claim one target, is
[Symlinks Manager](../reference/tools/symlinks.md).

## Package Management

**System Packages**: Homebrew (macOS), apt (Ubuntu/WSL, and generic Debian/Ubuntu LXCs), pacman (Arch)

**Language runtimes**: each through its own version manager — uv, rustup, the go tarball, and fnm for Node. None is subscribed to: a machine gets Go because it declared `go_tools` and Rust because it declared `cargo_packages`, so the runtime is derived from the tool lists that need it and `install/packages.yml` carries only its version floor.

**Why separate**: Version managers provide cross-platform consistency and project-specific versions without system conflicts.

## Machine Manifests

Installation is driven by machine manifests in `install/manifests/`. Each manifest defines exactly what gets installed. Every installed tool is declared as a name in a list; the name must resolve to a catalog entry in `install/packages.yml`. `dotfiles machines check` enforces this bidirectionally (every name → an entry, every entry → a name that references it or a warning).

```yaml
# install/manifests/archlinux-personal-workstation.yml
machine: archlinux-personal-workstation
platform: archlinux

function_groups: [core, git, python, aws, docker, network, reference, node, fzf]
alias_groups: [core]

system_packages: workstation   # or `core` for a minimal server (linux-lxc-server)
go_tools: [task, cheat, terraform-docs, ...]
github_releases: [fzf, neovim, lazygit, yazi, tree-sitter, tenv, ...]
custom_installers: [bats, awscli, claude-code, terraform-ls, ...]
cargo_packages: [bat, fd-find, eza, zoxide, ...]
npm_globals: [typescript-language-server, prettier, ...]
uv_tools: [ruff, mypy, basedpyright, ...]
git_uv_tools: [refcheck, indy, ...]
# ... etc
```

Runtime installation is **derived from list presence**, not from explicit booleans. A non-empty `go_tools:` list triggers the Go runtime install; a non-empty `npm_globals:` list triggers nvm + Node; `uv_tools:` or `git_uv_tools:` triggers uv. The deprecated `go: true` / `rust: true` / `nvm: true` / `uv: true` / `tenv: true` gates were removed in the Phase 1.6 cleanup — the manifest loader refuses any manifest that still sets them, naming the replacement.

Run installation with `bash install.sh --machine archlinux-personal-workstation`
for the CLI, then the `dotfiles apply --machine ...` it prints for the machine.

## Shell Source Files

Shell functions and aliases live in `shell/`, deployed via symlinks — no build step required.

- **Shared**: `shell/common/` → `~/.local/shell/`
- **Per coordinate**: `shell/<axis>/<value>/` → `~/.local/shell/<axis>/<value>/`, keeping the path so a sourced file says which coordinate asked for it
- **Machine-local**: `~/.local/shell/local.sh` — a real file that exists in no repo, described below

`.zshrc` sources `common/` and then globs `~/.local/shell/*/*/*.sh`, sourcing
every one it finds and `local.sh` last. It reads no list to decide which: the
symlink manager deploys only the directories this machine's coordinates select
and prunes the ones it no longer does, so the tree is the resolved answer. Most
of the six axes have no directory at all, because an axis earns one only where
something actually differs along it.

The axes replaced a single fused `PLATFORM` string, which could not say that the apt helpers belong to Ubuntu-on-WSL *and* to the Debian LXC, or that the Wayland config belongs to any Linux running it rather than to Arch. A `MACHINE_ROLE` axis (work, personal, server) was tried alongside `PLATFORM` and removed before the split: it was rendered from the same manifest, so it carried no information `MACHINE` did not, and it declared three values while shipping a single file that served a single machine. That file was employer infrastructure, which the machine-local file handles instead — a better fit, because that code was never shareable in the first place.

### The machine-local file

`~/.local/shell/local.sh` is shell code this repo declares but deliberately never contains, for the work box's employer infrastructure — internal hostnames, share paths, Okta profiles. It is a real file among the symlinks, sourced last so it can build on what the coordinate layers exported.

The repo knows it exists without knowing its contents. `install/flags.yml` declares it as a `required_files` entry narrowed to one machine, so `dotfiles env apply` names the path in the generated `~/.env` — which is what tells a rebuild where the file goes — and `dotfiles check` reports it missing. That is the same split as the `required:` values beside it, one level up: a required file rather than a required value.

It is restored by `safekeep`, not installed, so it is legitimately absent between `dotfiles apply` and the restore step of a rebuild. Both consumers guard on the file existing, and `relink` only removes symlinks that resolve into the repo, so a real file there survives every relink untouched.

The split to hold to is mechanism versus values: mounting a Windows share is a WSL capability, so `mount-cifs` lives in `shell/host/wsl/wsl.sh` and takes the share as an argument. Only the wrappers naming actual hosts go in `local.sh`.

A second test sits beside it, and it is the one that is easy to miss: a workaround only an employer's network forces is theirs too, however generic it looks. `update-tldr` installs tldr pages from a zip downloaded by hand, and read as a mechanism it is plainly a WSL function — it reaches the Windows Downloads folder through `$winchris`. But no personal WSL box would ever run it, because every one of them can just fetch the pages. It sat in the layer for months on the strength of the mechanism test alone.

### The register, and the backup that feeds it

`required:` and `required_files:` together are the whole set of things a machine needs that `apply` will never supply, and `dotfiles machines requirements` is the listing. It answers for any machine including one you are not standing on, so it reports only what is declared and never whether a file is there; `dotfiles check` is the half that looks.

Each entry carries a `restore:` — how to get that one back — defaulting to safekeep. The default is wrong for exactly one entry and that is the point of the key: `~/.config/safekeep/` on a machine with no backup yet cannot be restored from the backup it configures, so it declares `safekeep config init` instead. Declaring the safekeep config at all was what surfaced the Arch box having none, and therefore backing up nothing.

### A machine answers in more than one place

`~/.env` is a shell file, so everything that answers from it is a shell — and the scheduled check is not one. A systemd user unit and a LaunchAgent both start from an environment that has never sourced a profile, so an entry declared through a variable resolved to that literal string and the timer reported the repo registry missing four times a day, advising a safekeep restore of a file that was sitting on disk. The variable was never the problem; the assumption that a shell had run was.

So a declared name resolves through more than one rung, and the lowest is a config file a process with no shell can still read. The order, why it is that order, and why there is no compiled-in default under it are the module docstring in `src/dotfiles/settings.py`, which is the resolver; `standards/data.md` § "A shared file is named in config; only the tool's own default is compiled in" is the rule it implements. `dotfiles config show` prints what each one resolved to on this machine and which rung answered.

A rung between those two was deleted rather than reordered: a single unprefixed variable naming a shared file for every tool that reads it. It was exported from `~/.env`, so it was empty in exactly the unattended runs the config file exists for, and a tool reading an unprefixed name cannot tell its own file from somebody else's. Each tool now reads only its own `<TOOL>_`-prefixed variable above its own config key. The repo registry is the file that variable named, and it is no longer in the register at all — a trust variant deploys `repos_registry` into each tool's config, because where the registry lives is a fact about the trust domain rather than about one machine. `validate._registry_paths` is what holds those copies to one answer, since the deploy model has no templating to write the path once.

That split is also why a missing file reports two different findings. *Nothing names its location* is a machine that never answered, and the advice names every place it could; *absent at a path, from a named rung* is a machine that answered and has no file there, which is the state between an install and safekeep's restore. Only the second is something safekeep can fix, and reporting both as the first is what made the timer's advice wrong. They share a verdict, so the rung is carried as a field on the finding rather than a phrase inside it — the report is read by `--json` as well as by a person.

The prefixed spelling is for shared files only. `WINDOWS_USER` and `WINDOWS_DOMAIN` take no `DOTFILES_` twin and no config key, because a Windows account name is a fact about the machine rather than a setting of this tool — prefixing it would claim a name that is not ours, and the shell code reading it would not find the prefixed one.

`--safekeep` emits the register as the `[[back_up_paths]]` blocks safekeep's config wants, every one tagged `dotfiles` so `safekeep restore --tag dotfiles` is exactly this set. A block to paste rather than a generated config, and that boundary is load-bearing: required-to-operate is a strict *subset* of worth-backing-up, so generating the whole file from the register would silently drop `~/.ssh` and everything else the repo has no opinion about. What can be generated is the part the repo can prove. Required *values* have no path and survive as a trailing comment rather than being dropped — a rebuild that restores every file and none of them still has a broken machine, and this is the only listing that knows both halves.

The Windows box takes the same files by a different write. Its admin policy refuses to create a symlink, so the machine declares `deploy_by_copy` and the symlink manager copies each declared file to its target instead of linking it. That is the mechanism the whole tree goes through — `configs/`, `apps/` and `shell/` alike — and [Symlinks Manager](../reference/tools/symlinks.md) holds what it gives up: a copy is a regular file, so provenance is gone, and with it the foreign-target refusal, `--force` and the orphan prune. Nothing is ever removed there, because a file at a path the repo no longer declares is either a copy left behind or the only copy of something the user put there, and nothing on disk says which.

This is inherited reasoning rather than new. Windows Git Bash cannot follow a symlink across the WSL boundary either, so for as long as the Windows side was reached from WSL a script copied the files across and wrote the `.bashrc` that loaded them. It sourced each file separately rather than concatenating them into one `combined.sh` for startup speed, which measured at ~0.1ms of saved file opens against a ~60ms startup and turned one syntax error into a shell with no aliases or functions at all. It also refused to delete, for exactly the reason the copy mode still refuses to prune.

What that arrangement could not do is anything else a machine needs. It carried shell files and `~/.env` and nothing more, because the Windows side was not a machine this repo could address — it had no manifest, no coordinates and no way to run the CLI. Declaring it as one replaced the bridge with an ordinary `dotfiles apply`, and the group of verbs that reached across the boundary was deleted rather than kept beside it: two owners of one act is how a machine comes to disagree with itself about what has run.

## What a machine is, and who says so

Nothing detects it. `MACHINE` is the one hand-chosen value; it selects a
manifest, and the manifest declares where the machine sits on each of the six
axes in `src/dotfiles/coordinates.py`. `dotfiles env apply` resolves that point
into the `<axis>/<value>` directories it selects and writes them into `~/.env`
and deploys them. Nothing about that point reaches `~/.env`.

No coordinate variable at all, which took two goes to arrive at. Six existed
first, one per axis, so each shell could reassemble a list `Coordinates.directories`
had already built — six exports and two hand-written loops spelling the axis
names again, with nothing holding either copy to `AXIS_DIRS`. Collapsing them
to one resolved list fixed the disagreement between the copies and left the copy
itself. That list named six directories on a machine that had one, because it
recorded what the coordinates *select* while the tree holds what actually
differs. A shell that globs the tree needs neither.

Detection was tried and is what the declaration replaced: a wsl manifest whose
`~/.env` was missing fell back to a guess and deployed the linux shell layer
for a whole install. A guess also cannot answer half the axes — nothing on a box
knows whether it is on a fleet or nonfleet network, or whether it is meant to be a
workstation or a server.

`dotfiles machines show <name>` prints the resolved tuple for any manifest,
including ones this machine is not.

## Configuration Variants

`configs/` deploys variants, never a merge: exactly one file arrives at each
destination and the rest are versions this machine did not select. Git is the
exception, and it builds its own layering on top of what arrived — the deployed
files are chained together by `include.path`, last-wins.

**Example: Git Config**

`~/.config/git/config` is the entry point and the only file in that directory the repo does not
own. It is a real file holding a single include of `common.gitconfig`, written by the deploy
epilogue, and it must be real rather than a symlink for two reasons: git writes there when
`~/.gitconfig` is absent, and it follows a symlink when writing, so an entry point linked into the
checkout would commit an identity into the repo the first time anyone followed git's own "Please
tell me who you are" hint.

Everything shared — delta, the nvim mergetool, aliases, `pull.rebase` — ships from
`configs/common/.config/git/common.gitconfig`. Below it sits one include per variant, each named for
the coordinate **value** that supplies it rather than the axis: `wsl.gitconfig` carries
`core.autocrlf` from `configs/host/wsl/`, because a checkout on the Linux side is edited from
Windows tools too, and `fleet.gitconfig` or `nonfleet.gitconfig` carries identity. All are ignored
while absent, so a machine needing none ships nothing. Trust comes last because its nonfleet form
overrides a default with an `includeIf`, and git resolves last-wins.

Naming the value is what makes `ls ~/.config/git/` answer what the machine is. `trust.gitconfig`
said only that the trust axis had been resolved; `nonfleet.gitconfig` says which way. The cost is
that `common.gitconfig` has to spell every value out, because git expands nothing but `~` in an
`include.path` — `.zshrc` reaches its own layers by globbing the deployed tree and needs no list,
which is the asymmetry that lets `shell/` keep `<axis>/<value>/` in its deployed path while
`configs/` flattens. `dotfiles machines check` fails on a variant gitconfig no include names, since
git would otherwise ignore the missing line without a word.

The `gh` credential helper used to be in that variant and is now common, which is what collapsed
three near-identical files into one. It was per-platform only because it named an absolute path —
`/usr/bin/gh` on Linux, `/usr/local/bin/gh` on an Intel Mac, and `/opt/homebrew/bin/gh` on an Apple
Silicon one, a distinction no platform string draws. `gh` unqualified resolves everywhere git runs
here.

Identity rides the trust axis, because that is the thing it actually varies with: a machine hosting
employer work alongside personal needs a different default from one hosting only personal work.
A fleet machine's `fleet.gitconfig` includes `personal.gitconfig` unconditionally, so the three
personal machines take their identity from the repo and nobody sets one by hand. The personal
address is in the repo because it is already in every commit object here — shipping it discloses
nothing, and a value the repo owns cannot drift on one machine or vanish when a symlink is pruned.

A machine off the fleet inverts the pair: `local.gitconfig` is the default, and `personal.gitconfig`
is included behind `includeIf "hasconfig:remote.*.url:..."`. That direction is deliberate — a repo
slipping through the match commits under the employer address, which is wrong but internal, where
the reverse puts a personal address into employer history. `hasconfig` keys on the remote rather
than the checkout path, so it holds wherever a repo is cloned; it takes two blocks because the
condition matches the URL literally and HTTPS and SSH spell the same remote differently.

Four levels of include is more than prose can keep anyone oriented in, so
`dotfiles identity show` draws the chain this machine actually resolved — which file
contributed what, which variant is legitimately absent, and which conditional include did not fire
here. `dotfiles check` reports the two ways the arrangement fails silently: a `~/.gitconfig`, which
git prefers over the entry point for reads and writes both, and one key given different values by
two different files, where nothing on screen says which one won.

`local.gitconfig` is the one identity the repo does not ship, so `install/flags.yml` declares it
and `dotfiles check` fails while it is missing. That declaration is load-bearing: git ignores an
absent include silently, and `user.useConfigOnly = true` would then refuse every commit while
naming nothing. For the same reason the check runs `git config --global --includes --get` —
`--global` alone implies `--no-includes` and would report every machine unset, and the pair
deliberately ignores the `includeIf` so it reports the machine's default rather than whatever the
current directory resolves to.

**Example: Neovim**

Common (`configs/common/.config/nvim/`): Base LSP, core plugins, keybindings

Platform-specific (optional): platform LSP configs

## Design Decisions

**Symlinks over Stow**: Custom tool provides better two-level linking, clearer error messages, platform awareness.

**Taskfile over Makefile**: Cross-platform consistency, better syntax for complex commands, modular includes, self-documenting.

**Version Managers for Languages**: Same Node/Python versions across platforms, project-specific versions, no system conflicts.

**Unified Theme System**: The `theme` CLI generates consistent configs for ghostty, tmux, btop, and Neovim from a single `theme.yml` source file per theme.

## The cost of the split

The common-plus-coordinate scheme buys one shared edit reaching every platform, and charges
one recurring question: does this belong in `configs/common/` or in the platform
directory? Getting it wrong is quiet — a setting lands in `common/` that only
one OS can honour, and the others carry it harmlessly until the day one does
not.

The test is whether the *other* platforms would want it if they could run it. A
`.gitconfig` alias belongs in common even though only one machine uses that
remote; a Homebrew path does not, because it is meaningless elsewhere rather
than merely unused. See
[Platform Differences](../reference/platforms/differences.md).

## Where to go next

The sidebar lists every architecture page; these are the three that answer the
questions asked most often.

[Management Interface](management-interface.md) is the one to read first — the
two front doors, why `plan` and `check` are different questions, and what
`~/.env` decides.
[Package Management](package-management.md) is which installer a tool gets and
why. [Observability](observability.md) is what a run leaves behind and who reads
it, which is where to start when something reported a machine wrongly.
