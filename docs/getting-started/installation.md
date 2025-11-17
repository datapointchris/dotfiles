# Installation

Cross-platform installation for macOS, WSL Ubuntu, and Arch Linux. Each platform uses a bootstrap script that installs prerequisites (Homebrew on macOS, Taskfile on all platforms) then delegates to the Task automation system for package installation.

## Quick Install

Clone the repository and run the platform-specific bootstrap script:

=== "macOS"

    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/macos-setup.sh
    ```

    **Time**: ~20-30 minutes (includes Homebrew installation)

=== "WSL Ubuntu"

    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/wsl-setup.sh
    ```

    **Time**: ~15-20 minutes

    **Required**: Set `ZSHDOTDIR` in `/etc/zsh/zshenv`:

    ```bash
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

=== "Arch Linux"

    ```bash
    git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
    cd ~/dotfiles
    bash management/arch-setup.sh
    ```

    **Time**: ~15-20 minutes

    **Required**: Set `ZSHDOTDIR` in `/etc/zsh/zshenv`:

    ```bash
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

After installation completes, restart your terminal or run `exec zsh` to load the new configuration.

## How Installation Works

All platforms follow the same two-step pattern:

1. **Bootstrap script** - Installs minimal prerequisites needed to run Task
2. **Task automation** - Handles all package installation and configuration

This separation keeps bootstrap scripts simple and makes the installation fully reproducible via Task.

## Platform-Specific Details

=== "macOS"

    ### Bootstrap Script

    `management/macos-setup.sh` performs these steps:

    1. Install Homebrew if not present (Apple Silicon: `/opt/homebrew`, Intel: `/usr/local`)
    2. Install Taskfile via Homebrew
    3. Run `task install-macos` for complete package installation

    ### Package Installation

    `task install-macos` installs:

    - System packages via Homebrew (CLI tools, GUI applications)
    - Version managers (nvm for Node.js, uv for Python)
    - Shell configuration (zsh plugins, starship prompt)
    - Custom Go applications (sess, toolbox)
    - Symlink dotfiles to home directory
    - Configure theme system (tinty + theme-sync)
    - Install tmux and neovim plugins

    ### Platform Notes

    **GNU Coreutils**: Installed with `g` prefix (gls, gsed, gtar) to avoid conflicts with BSD versions. Not added to PATH by default - use Task commands when needed or prefix commands with `g`.

    ### Post-Install Steps

    **Nerd Font**: Required for proper terminal icons and glyphs. Download from [nerdfonts.com](https://www.nerdfonts.com/).

    Recommended fonts: FiraCode Nerd Font, JetBrainsMono Nerd Font, Hack Nerd Font

    Install by double-clicking font files or copying to `~/Library/Fonts/`:

    ```bash
    cp /path/to/your/fonts/*.{ttf,otf} ~/Library/Fonts/
    ```

    See [Fonts](fonts.md) for detailed font installation and configuration.

    **Set zsh as default shell** (if not already):

    ```bash
    chsh -s $(which zsh)
    ```

    **Restart terminal** to load the new configuration, or run `exec zsh` in your current session.

=== "WSL Ubuntu"

    ### Bootstrap Script

    `management/wsl-setup.sh` performs these steps:

    1. Install Taskfile (downloads GitHub release binary)
    2. Run `task install-wsl` for complete package installation

    ### Package Installation

    `task install-wsl` executes 9 phases sequentially:

    1. **System Packages (apt)** - Core utilities (zsh, tmux, ripgrep, jq, multimedia tools)
    2. **GitHub Release Tools** - Latest stable binaries (yq, Go 1.23+, fzf 0.66+, neovim 0.11+, lazygit, yazi)
    3. **Rust/Cargo Tools** - Pre-compiled binaries via cargo-binstall (bat, fd, eza, zoxide, delta, tinty)
    4. **Language Package Managers** - nvm (Node.js), uv (Python)
    5. **Shell Configuration** - Zsh plugins (fast-syntax-highlighting, autosuggestions, fzf-tab)
    6. **Custom Go Applications** - Build and install sess and toolbox
    7. **Symlinking Dotfiles** - Deploy configs to home directory
    8. **Theme System** - Initialize tinty themes
    9. **Plugin Installation** - Tmux plugins (TPM) and Neovim plugins (lazy.nvim)

    ### Platform Notes

    **Why GitHub releases and cargo-binstall instead of apt?** We prioritize latest versions and cross-platform consistency over using only system package managers:

    - **fzf**: GitHub release has 0.66.1 vs apt's 0.44.1 (22 versions ahead!)
    - **neovim**: GitHub release has 0.11+ vs apt's 0.9.5
    - **Go**: GitHub release has 1.23+ vs apt's 1.22
    - **Rust tools**: cargo-binstall provides pre-compiled binaries with correct names (`bat` not `batcat`, `fd` not `fdfind`)

    System utilities like zsh, tmux, and ripgrep come from apt because they're stable, well-tested, and don't need frequent updates. See [Package Version Analysis](../learnings/package-version-analysis.md) for detailed comparison.

    **ZSHDOTDIR requirement**: WSL requires explicit configuration in `/etc/zsh/zshenv` to set the zsh configuration directory. This is intentional - we use XDG-compliant directory structure (`~/.config/zsh/`) instead of cluttering the home directory with `.zshrc`.

    ```bash
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

    ### Post-Install Steps

    **ZSHDOTDIR verification**: If zsh doesn't start properly or configs aren't loading, verify `/etc/zsh/zshenv` contains the ZSHDOTDIR export shown above.

    **Nerd Font** (optional): WSL can use Windows fonts, so you have two options:

    **Option 1 - Install in Windows** (recommended, easiest):

    - Download fonts from [nerdfonts.com](https://www.nerdfonts.com/)
    - Right-click font files → "Install for all users"
    - WSL automatically has access to Windows fonts

    **Option 2 - Install in WSL**:

    ```bash
    mkdir -p ~/.local/share/fonts
    cp /path/to/your/fonts/*.{ttf,otf} ~/.local/share/fonts/
    fc-cache -fv
    ```

    See [Fonts](fonts.md) for detailed font installation.

    **WSL restart** (if you modified `/etc/wsl.conf` during installation):

    ```bash
    wsl.exe --shutdown
    ```

    Then reopen WSL terminal.

    **Restart terminal** to load the new configuration, or run `exec zsh` in your current session.

=== "Arch Linux"

    ### Bootstrap Script

    `management/arch-setup.sh` performs these steps:

    1. Install Taskfile (downloads GitHub release binary)
    2. Install yay if not present (AUR helper)
    3. Run `task install-arch` for complete package installation

    ### Package Installation

    `task install-arch` installs:

    - System packages via pacman (zsh, tmux, neovim, ripgrep, etc.)
    - AUR packages via yay (additional tools not in official repos)
    - Version managers (nvm for Node.js, uv for Python)
    - Shell configuration (zsh plugins, starship prompt)
    - Custom Go applications (sess, toolbox)
    - Symlink dotfiles to home directory
    - Configure theme system (tinty + theme-sync)
    - Install tmux and neovim plugins

    ### Platform Notes

    **ZSHDOTDIR requirement**: Same as WSL, Arch requires explicit ZSHDOTDIR configuration:

    ```bash
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

    **AUR Helper**: yay is installed automatically for packages not in official repositories.

    ### Post-Install Steps

    Follow the same post-install steps as WSL for fonts and terminal restart.

## Verification

After installation completes, verify that key tools are working:

```bash
task --list           # Should show available tasks
toolbox list          # Should show installed tools with descriptions
theme-sync current    # Should show current theme
node --version        # Should show Node.js version (via nvm)
uv --version          # Should show uv version
```

If any commands fail, see [Troubleshooting](../reference/troubleshooting.md).

## What Gets Installed

**Package Managers**:

- macOS: Homebrew
- WSL Ubuntu: apt (system), cargo-binstall (Rust tools)
- Arch Linux: pacman (official), yay (AUR)

**Version Managers** (cross-platform consistency, avoid system package conflicts):

- nvm (Node.js version management)
- uv (Python version management, project dependencies, virtual environments)
- cargo-binstall (Rust pre-compiled binaries)

**CLI Tools** (30+ tools, organized by installation method):

- **Rust Tools** (cargo-binstall → `~/.cargo/bin`): bat, fd, eza, zoxide, git-delta, tinty
- **GitHub Releases** (→ `~/.local/bin`): fzf, neovim, lazygit, yazi, yq, Go
- **System Packages** (brew/apt/pacman): zsh, tmux, ripgrep, jq, tree, htop
- **Language Servers** (npm global): typescript-language-server, bash-language-server, yaml-language-server
- **Custom Apps** (Go → `~/go/bin`): sess (session manager), toolbox (tool discovery)

Run `toolbox list` to see all installed tools with descriptions and categories.

**Theme System**:

- tinty (Base16 theme manager)
- theme-sync (custom wrapper script for applying themes across tmux, bat, fzf, shell)
- 12 curated favorite themes (rose-pine, gruvbox-dark-hard, kanagawa, nord, etc.)

**Automation**:

- Taskfile (task runner for coordinating installation, updates, and maintenance)
- Modular taskfiles in `management/taskfiles/` for different concerns

See [PATH Ordering Strategy](../architecture/path-ordering-strategy.md) to understand how tool resolution priority works across different installation methods.

## Manual Installation

If the bootstrap script fails or you already have Task installed, run the installation tasks directly:

```bash
cd ~/dotfiles

# Auto-detect platform and install
task install

# Or specify platform explicitly:
task install-macos
task install-wsl
task install-arch
```

This approach is useful for:

- Re-running installation after bootstrap script issues
- Updating packages without re-running bootstrap
- Installing on systems where you already have Task configured

## Next Steps

After installation completes:

1. **Configure zsh**: See [First Configuration](first-config.md) for customizing shell aliases, functions, and prompt
2. **Install fonts**: See [Fonts](fonts.md) for Nerd Font installation and terminal configuration
3. **Explore tools**: Run `toolbox search <query>` to discover installed tools by category
4. **Try themes**: Run `theme-sync favorites` to see available themes, then `theme-sync apply <name>` to switch

## Troubleshooting

See [Troubleshooting Guide](../reference/troubleshooting.md) for common installation issues and solutions.
