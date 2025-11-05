# Installation

Platform-specific installation instructions.

## macOS

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/macos-setup.sh
```

Bootstrap script installs Homebrew and Taskfile, then runs `task install-macos`.

Time: ~20-30 minutes

**GNU Coreutils**: Installed with `g` prefix (gls, gsed, gtar). Not in PATH by default to avoid BSD conflicts.

**Homebrew Location**:

- Intel: `/usr/local`
- Apple Silicon: `/opt/homebrew`

## WSL Ubuntu

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/wsl-setup.sh
```

Bootstrap script installs Taskfile, then delegates all package installation to `task install-wsl`.

Time: ~15-20 minutes

**ZSHDOTDIR Required**: Add to `/etc/zsh/zshenv`:

```sh
echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
```

**Binary Symlinks**: Script creates symlinks for `batcat` → `bat` and `fdfind` → `fd`.

**Cargo Tools**: Installs eza, yazi, git-delta via cargo (not available in apt).

## Arch Linux

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/arch-setup.sh
```

Bootstrap script installs Taskfile, then delegates all package installation to `task install-arch`.

Time: ~15-20 minutes

**ZSHDOTDIR Required**: Add to `/etc/zsh/zshenv`:

```sh
echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
```

**AUR Helper**: yay is installed automatically.

## Verification

```sh
task --list           # Should show available tasks
tools list            # Should show installed tools
theme-sync current    # Should show current theme
node --version        # Should show Node.js version
uv --version          # Should show uv version
```

Restart terminal: `exec zsh`

## What Gets Installed

**Package Managers**: Homebrew (macOS), apt (Ubuntu), pacman (Arch)

**Version Managers**: nvm (Node.js), uv (Python)

**CLI Tools**: bat, eza, fd, ripgrep, fzf, zoxide, yazi, lazygit, tmux, neovim, git-delta, and more. Run `tools list` for complete list.

**Theme System**: tinty + theme-sync script

**Automation**: Taskfile for coordination tasks

## Manual Alternative

If bootstrap script fails or you already have task installed:

```sh
cd ~/dotfiles
task install          # Auto-detects platform
# Or specific platform:
task install-macos
task install-wsl
task install-arch
```

## Troubleshooting

See [Troubleshooting Guide](../reference/troubleshooting.md) for common issues.
