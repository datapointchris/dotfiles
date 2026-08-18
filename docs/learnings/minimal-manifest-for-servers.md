# Minimal Manifest for LXC Servers and Small Linux Boxes

## The Problem

For a stretch the install system shipped only heavy `*-personal-workstation`
manifests, so a headless LXC or small Linux box had no supported install path.
Every manifest was a full workstation profile. The reflex of pointing a small box
at one installed the entire workstation payload — every npm/cargo/uv tool plus
docker, ffmpeg, and other desktop packages a server never needs.

A `ubuntu-lxc-server` platform once existed and was removed in `a3378fd9` as
"never used." That was true at that instant. The homelab LXC fleet then made a
small Linux box the *most common* deployment target, so the rationale inverted and
the gap bit repeatedly.

## The Solution

One minimal manifest, plus a tiered system-package model.

- **`install/manifests/linux-lxc-server.yml`** — the one minimal profile. It exists
  to be SSHed into and diagnosed from, so every tool list on it is deliberately
  short, and there is no npm or uv tooling and no GUI installer at all. Read the
  manifest for what it carries; each line there says why that tool is on a server.

- **System-package tiers, one list.** Each entry in `system_packages`
  (`install/packages.yml`) may carry `tier: core`; untagged entries default to
  workstation-only. `Subscription.wants` in `src/dotfiles/machine.py` filters the
  single list against the tier — a server installs only the tagged base, a
  workstation installs everything. There is no parallel list to drift. Manifests
  declare their tier via `system_packages: core|workstation`.

- **Optional coordinate directories.** The server ships only a shell layer and no
  configs of its own, and the symlinks manager treats every coordinate directory as
  optional. They are keyed on coordinates rather than on a platform string, so the
  apt helpers are `shell/pkg/apt/apt.sh` and reach the Ubuntu work box too — see
  `docs/reference/tools/symlinks.md`.

Provision one with `install.sh --machine linux-lxc-server`. The interactive zsh
layers are globbed from the deployed tree under `~/.local/shell/`, which
`dotfiles symlinks apply` resolves from the manifest — the shell is told what to
load rather than asked to work it out, and `~/.env` carries no coordinate to
disagree with it. See `docs/architecture/management-interface.md` § "The machine
environment".

## Key Learnings

1. **"Unused today" is not "unneeded."** Usage is a snapshot; deployment needs
   change. Before deleting the only lightweight profile, ask what provisions the
   fleet, not just the workstations.
2. **A profile gap is invisible until you hit it.** Nothing in the existing code
   paths was broken — the failure was the *absence* of a path, so it resurfaced
   as a fresh surprise each time until it was made first-class.
3. **Default to the larger set when tiering.** Untagged system packages fall to
   workstation, so a heavy new package can never silently bloat a minimal server;
   adding it to servers is a deliberate `tier: core` opt-in.

## Related Files

- `install/manifests/linux-lxc-server.yml` — the minimal profile
- `install/packages.yml` — `system_packages` tier convention (`tier: core`)
- `src/dotfiles/machine.py` — `Subscription.wants`, where the tier narrows the single `system_packages` list
- `shell/pkg/apt/apt.sh` — the apt layer
- `src/dotfiles/resources/symlinks.py` — `sources()`, where a coordinate directory is optional
