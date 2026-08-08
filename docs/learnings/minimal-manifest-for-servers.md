# Minimal Manifest for LXC Servers and Small Linux Boxes

## The Problem

For a stretch the install system shipped only heavy `*-personal-workstation`
manifests, so a headless LXC or small Linux box had no supported install path.
Two failures compounded:

1. **No `linux` platform branch.** `detect_platform` resolves a generic
   (non-WSL, non-Arch) Linux host to the platform string `linux`, but
   `install.sh`'s platform `case` handled only `macos`, `wsl`, and `archlinux` —
   anything else fell through to `die "Unsupported platform: linux"`.

2. **No lean manifest.** Even past dispatch, every manifest was a full
   workstation profile. The reflex of pointing a small box at a workstation
   manifest was the wrong platform *and* installed the entire workstation payload
   — every npm/cargo/uv tool plus docker, ffmpeg, and other desktop packages a
   server never needs.

A `ubuntu-lxc-server` platform once existed and was removed in `a3378fd9` as
"never used." That was true at that instant, but the homelab LXC fleet makes a
small Linux box the *most common* deployment target, so the rationale inverted
and the gap bit repeatedly.

## The Solution

A first-class `linux` platform plus a tiered system-package model:

- **`install/manifests/linux-lxc-server.yml`** — the one minimal profile.
  `platform: linux`, `flatpak: false`, `system_packages: core`, and short tool
  lists chosen for common work and SSH diagnosis (shell + tmux + neovim, fzf,
  lazygit, yazi, glow, `gdu`/`duf` for disk, `bat`/`fd`/`eza`/`zoxide`, `oxker`,
  `sops`). No npm/uv tooling, no GUI installers.

- **System-package tiers, one list.** Each entry in `system_packages`
  (`install/packages.yml`) may carry `tier: core`; untagged entries default to
  workstation-only. `parse_packages.py --tier core|workstation` filters the
  single list — a server installs only the tagged base, a workstation installs
  everything. There is no parallel list to drift. Manifests declare their tier
  via `system_packages: core|workstation`.

- **Platform wiring.** `install.sh` and `update.sh` gained a `linux` branch
  (apt, no GUI/flatpak/preferences steps), the Taskfile resolves a generic Linux
  host to `linux`, and `install/linux/system-packages.sh` installs the core tier.

- **Optional overlays.** The server ships only a shell overlay and no configs of
  its own, and the symlinks manager treats every overlay as optional. Those
  overlays are keyed on coordinates now rather than on the platform string, so
  the apt helpers this called `shell/linux/linux.sh` are `shell/pkg/apt/apt.sh`
  and reach the Ubuntu work box too — see `docs/reference/tools/symlinks.md`.

Provision one with `install.sh --machine linux-lxc-server`. The interactive zsh
overlays load from the `DOTFILES_*` coordinates in `~/.env`, which the install
writes from the manifest rather than leaving to be typed by hand — see
`docs/architecture/management-interface.md` § "The machine environment".

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
4. **Platform dispatch and manifests are two gates.** A manifest is useless
   without a `case` branch for its platform, and vice versa — they must land (and
   be removed) together.

## Related Files

- `install/manifests/linux-lxc-server.yml` — the minimal profile
- `install/packages.yml` — `system_packages` tier convention (`tier: core`)
- `src/dotfiles/parse_packages.py` — `get_system_packages(..., tier)` and `--tier`
- `install.sh` / `update.sh` — `linux` platform branch and tier gating
- `shell/pkg/apt/apt.sh` — the apt overlay these helpers moved to
- `src/dotfiles/resources/symlinks.py` — `layers()`, where an overlay is optional
