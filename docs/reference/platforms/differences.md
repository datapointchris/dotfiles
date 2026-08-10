# Platform Differences

Which manifest a machine uses, and the handful of ways the platforms genuinely
diverge.

| Aspect | macOS | WSL Ubuntu | Arch Linux |
| --- | --- | --- | --- |
| **Package Manager** | brew | apt | pacman |
| **System Binaries** | /usr/local/bin, /opt/homebrew/bin | /usr/bin | /usr/bin |
| **Machine Manifest** | macos-personal-workstation | wsl-work-workstation | archlinux-personal-workstation |

`~/.local/bin` is the user binary directory everywhere, and binary names are
consistent everywhere — the Ubuntu `batcat`/`fdfind` problem does not arise
because `bat` and `fd` install through `cargo binstall` rather than apt. That
consistency is the point of the [package
strategy](../../architecture/package-management.md), not an accident.

A headless LXC or small Linux box uses the separate `linux-lxc-server` manifest
(platform `linux`), a minimal profile installed with
`install.sh --machine linux-lxc-server` and the `dotfiles apply` it prints. It
installs the `core` system-package
tier — the lean base tagged in `packages.yml`, without the docker/media/GUI
packages the workstation manifests pull in. Do not point a small box at a
workstation manifest; see
[Minimal Manifest for Servers](../../learnings/minimal-manifest-for-servers.md).

Platform-specific quirks that needed a decision — the atuin split, fnm over
nvm, the npm prefix — are in [Tool Availability](tools.md).
