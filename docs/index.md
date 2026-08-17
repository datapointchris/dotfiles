# Dotfiles

Cross-platform machine configuration for macOS, WSL Ubuntu, and Arch Linux.
Manifest-driven installation, with shared configs and one directory per machine
coordinate beside them.

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

## Finding things

Every tool has `--help`, and that is the reference for its flags. For what
exists rather than how to call it:

```bash
task --list-all      # every task (from inside the repo)
dotfiles --help      # the same operations, from anywhere
doit kit list        # everything indexed, by collection
doit find <term>     # search tools, functions, aliases and keybindings at once
theme list
```

If something is broken, [Troubleshooting](reference/support/troubleshooting.md)
opens with the three commands that diagnose most of it, and
`rg -i "<the error>" docs/learnings/` searches the debugging record by symptom.
