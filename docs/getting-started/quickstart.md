# Quick Start

## Installation

=== "macOS"
    ```sh
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash scripts/install/macos-setup.sh
    ```

    Installs Homebrew (if needed), Taskfile, then runs full installation.

    Time: ~20-30 minutes

=== "WSL Ubuntu"
    ```sh
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash scripts/install/wsl-setup.sh
    ```

    Installs Taskfile, then delegates to `task install-wsl` for full installation.

    Time: ~15-20 minutes

    WSL requires `ZSHDOTDIR` set in `/etc/zsh/zshenv`:
    ```sh
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

=== "Arch Linux"
    ```sh
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash scripts/install/arch-setup.sh
    ```

    Installs Taskfile, then delegates to `task install-arch` for full installation.

    Time: ~15-20 minutes

## Verify

```sh
task --list           # Should show available tasks
tools list            # Should show installed tools
theme-sync current    # Should show current theme
```

Restart terminal or run `exec zsh` to load configs.

## Try It Out

```sh
# Explore tools
tools search git
tools show bat

# Switch themes
theme-sync favorites
theme-sync apply base16-gruvbox-dark-hard

# Update packages
task update
```

## What Gets Installed

**Version Managers**:

- nvm (Node.js)
- uv (Python)

**CLI Tools**: bat, eza, fd, ripgrep, fzf, zoxide, yazi, lazygit, tmux, neovim, etc. Run `tools list` to see all.

**Theme System**: tinty + theme-sync command for Base16 themes

**Automation**: Taskfile for coordination tasks

See [Installation Guide](installation.md) for details.
