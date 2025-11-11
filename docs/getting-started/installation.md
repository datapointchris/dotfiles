# Installation

Platform-specific installation instructions.

## macOS

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash management/macos-setup.sh
```

Bootstrap script installs Homebrew and Taskfile, then runs `task install-macos`.

Time: ~20-30 minutes

**GNU Coreutils**: Installed with `g` prefix (gls, gsed, gtar). Not in PATH by default to avoid BSD conflicts.

**Homebrew Location**:

- Intel: `/usr/local`
- Apple Silicon: `/opt/homebrew`

### Post-Install (macOS)

**Nerd Font**: Required for proper terminal icons. Download from [nerdfonts.com](https://www.nerdfonts.com/).

Recommended fonts: FiraCode Nerd Font, JetBrainsMono Nerd Font, Hack Nerd Font.

Install by double-clicking font files or copying to `~/Library/Fonts/`:

```sh
cp /path/to/your/fonts/*.{ttf,otf} ~/Library/Fonts/
```

**Set zsh as default shell** (if not already):

```sh
chsh -s $(which zsh)
```

**Restart terminal**: After installation, restart your terminal or run `exec zsh` to load new configuration.

## WSL Ubuntu

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash management/wsl-setup.sh
```

Bootstrap script installs Taskfile, then delegates all package installation to `task install-wsl`.

Time: ~15-20 minutes

**Installation Phases**: The installation is organized into 9 distinct phases:

1. **System Packages (apt)** - Core utilities (zsh, tmux, ripgrep, multimedia tools)
2. **GitHub Release Tools** - yq, Go, fzf, neovim, lazygit, yazi
3. **Rust/Cargo Tools** - bat, fd, eza, zoxide, delta, tinty (via cargo-binstall)
4. **Language Package Managers** - nvm, npm, uv
5. **Shell Configuration** - ZSH plugins
6. **Custom Go Applications** - sess, toolbox
7. **Symlinking Dotfiles** - Link configs to home directory
8. **Theme System** - tinty themes
9. **Plugin Installation** - Tmux and Neovim plugins

**ZSHDOTDIR Required**: Add to `/etc/zsh/zshenv`:

```sh
echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
```

**Universal Installation Strategy**: We prioritize latest versions and cross-platform consistency:

- **cargo-binstall** (Rust CLI tools) - Pre-compiled binaries, latest versions, no naming conflicts
  - `bat` (not `batcat`), `fd` (not `fdfind`), `zoxide`, `eza`, `git-delta`, `tinty`

- **GitHub Releases** (Core tools) - Latest stable versions
  - `go` (1.23+ vs apt's 1.22)
  - `fzf` (0.66.1 vs apt's 0.44.1 - **22 versions ahead!**)
  - `neovim` (0.11+ vs apt's 0.9.5)
  - `lazygit`, `yazi`, `yq`

- **apt** (System utilities) - Stable, infrequent updates
  - `zsh`, `tmux`, `ripgrep`, `jq`, multimedia tools (ffmpeg, imagemagick, etc.)

See [Package Version Analysis](../learnings/package-version-analysis.md) for detailed comparison and rationale.

### Post-Install (WSL Ubuntu)

**ZSHDOTDIR Configuration**: If zsh doesn't start properly, ensure `/etc/zsh/zshenv` contains:

```sh
echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
```

**Nerd Font** (Optional): WSL can use Windows fonts.

**Option 1** - Install in Windows (easiest):

- Right-click font files → "Install for all users"
- WSL automatically has access

**Option 2** - Install in WSL:

```sh
mkdir -p ~/.local/share/fonts
cp /path/to/your/fonts/*.{ttf,otf} ~/.local/share/fonts/
fc-cache -fv
```

**WSL Configuration**: If you modified `/etc/wsl.conf` during installation, restart WSL:

```sh
wsl.exe --shutdown
```

**Restart terminal**: After installation, restart your terminal or run `exec zsh` to load new configuration.

## Arch Linux

```sh
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash management/arch-setup.sh
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
toolbox list          # Should show installed tools
theme-sync current    # Should show current theme
node --version        # Should show Node.js version
uv --version          # Should show uv version
```

Restart terminal: `exec zsh`

## What Gets Installed

**Package Managers**: Homebrew (macOS), apt (Ubuntu), pacman (Arch)

**Version Managers**: nvm (Node.js), uv (Python), cargo-binstall (Rust binaries)

**Build Toolchains**: Go (1.23+), Rust (rustup)

**CLI Tools** (organized by installation method):

- **Rust Tools** (cargo-binstall → `~/.cargo/bin`): bat, fd, eza, zoxide, git-delta, tinty
- **GitHub Releases** (→ `~/.local/bin`): fzf, neovim, lazygit, yazi, yq
- **System Packages** (apt/brew): zsh, tmux, ripgrep, jq, tree, htop
- **Language Servers** (npm): typescript-language-server, bash-language-server, yaml-language-server
- **Custom Apps** (Go → `~/go/bin`): sess, toolbox

Run `tools list` to see all 30+ installed tools with descriptions.

**Theme System**: tinty + theme-sync script

**Automation**: Taskfile for coordinating all installation phases

See [PATH Ordering Strategy](../architecture/path-ordering-strategy.md) to understand tool resolution priority.

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
