# Dotfiles

Cross-platform machine configuration for macOS, WSL Ubuntu, and Arch Linux.
Manifest-driven installation, with shared configs and one overlay per machine
coordinate on top.

## Install

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash install.sh --machine <manifest>
dotfiles apply --machine <manifest>
```

`install.sh` is a bootstrap and nothing more: it puts uv and the `dotfiles` CLI
on the box, then prints those commands rather than running one. Converging is a
separate decision because it is a long networked run, and it is worth seeing
`dotfiles plan` first on a machine whose downloads are firewalled.

The manifest decides what a machine gets. They are in `install/manifests/`, and
`eza -1 install/manifests/` is the current list — one per machine type, ranging
from a full workstation to `linux-lxc-server`, which installs only the `core`
package tier.

There are no manual prerequisites on any platform. The apply sets up Homebrew,
and writes `ZDOTDIR` into the system zshenv itself, picking `/etc/zsh/zshenv` or
`/etc/zshenv` per distro. Restart the terminal or `exec zsh` when it finishes.

Rebuilding a machine from scratch, including what the automation cannot do:
[Rebuilding a Machine](reference/rebuilding-a-machine.md).

## Structure

`configs/`, `apps/`, and `shell/` each layer `<axis>/<value>/` overlays over a
shared `common/` base — `eza -1 -D configs apps shell` shows which exist, and
most do not. An axis earns a directory only where something actually differs
along it. `MACHINE` is the only value chosen by hand anywhere in the repo; it
selects a manifest, and the manifest declares the coordinates.

`install/` handles provisioning — manifests in `install/manifests/`,
the Windows-side scripts WSL needs in `install/wsl/`, what those scripts share in
`install/common/lib/`, and every package in `install/packages.yml`.

Some tools are developed elsewhere and installed from GitHub rather than living
here: `toolbox` and `sesh` (Go), `theme` and `font` (cloned to
`~/.local/share/`), and the Python tools under `git_uv_tools`. The four install
patterns and when each applies are in
[App Installation Patterns](learnings/app-installation-patterns.md).

## Key concepts

- **Machine manifests** decide what installs where, and what `platform` a machine declares
- **Symlinks** deploy configs from the repo into `$HOME` — `dotfiles symlinks apply` after any rename or delete
- **Feature flags** (`install/flags.yml`) turn behaviour on per machine, tested with `flag_enabled`
- **Theme** applies one palette across ghostty, tmux, btop and Neovim
- **Composition** — tools emit parseable data and leave the UI to fzf, gum, or a script

## Finding things

Every tool has `--help`, and that is the reference for its flags. For what
exists rather than how to call it:

```bash
task --list-all      # every task (from inside the repo)
dotfiles --help      # the same operations, from anywhere
toolbox list         # installed tools, by category
doit find <term>     # search tools, functions, aliases and keybindings at once
theme list
```

If something is broken, [Troubleshooting](reference/support/troubleshooting.md)
opens with the three commands that diagnose most of it, and
`rg -i "<the error>" docs/learnings/` searches the debugging record by symptom.
