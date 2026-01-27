# Platform Differences

Comprehensive reference for platform-specific differences across macOS, Ubuntu, WSL Ubuntu, and Arch Linux.

## Quick Reference

| Aspect             | macOS          | Ubuntu (Server)   | WSL Ubuntu        | Arch Linux |
| ------------------ | -------------- | ----------------- | ----------------- | ---------- |
| **Package Manager**| brew           | apt               | apt               | pacman     |
| **Shell**          | zsh (default)  | bash (default)    | bash (default)    | bash       |
| **Binary Prefix**  | None           | Some (bat, fd)    | Some (bat, fd)    | None       |
| **User Binaries**  | ~/.local/bin   | ~/.local/bin      | ~/.local/bin      | ~/.local/bin |
| **System Binaries**| /usr/local/bin | /usr/bin          | /usr/bin          | /usr/bin   |
| **Machine Manifest**| macos-personal-workstation | ubuntu-lxc-server | wsl-work-workstation | arch-personal-workstation |

## Deep Dive

<!-- markdownlint-disable MD033 -->
<div class="grid cards" markdown>

- :material-package: **[Package Differences](packages.md)**

    Package name and binary name differences across platforms

- :material-console: **[Command Reference](commands.md)**

    Package manager commands and environment configuration

- :material-tools: **[Tool Availability](tools.md)**

    Tool support, version managers, and platform-specific quirks

</div>
<!-- markdownlint-enable MD033 -->
