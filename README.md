# Dotfiles

Modern, cross-platform dotfiles configuration featuring:

- **Shared Configuration Architecture**: DRY configuration with platform-specific customizations
- Standalone zsh setup with custom prompt and Nerd Font icons
- Smart directory navigation with zoxide
- Enhanced command-line tools (fzf, fd, eza, bat, yazi)
- Cross-platform compatibility (macOS, Ubuntu WSL, Arch Linux)

## Architecture

This dotfiles setup uses a **shared configuration** approach:

- `shared/` - Common configuration files used across all platforms
- `macos/` - macOS-specific configurations and symlinks
- `wsl/` - WSL-specific configurations and symlinks
- `ubuntu/` - Ubuntu-specific configurations and symlinks

Key shared files are symlinked from platform directories to maintain DRY principles while allowing platform-specific customizations.

## Quick Installation

```bash
# Clone the repository
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Link shared configuration to platform directories
./symlinks shared

# Link your platform's configuration to $HOME
./symlinks macos          # On macOS
./symlinks wsl            # On WSL
./symlinks ubuntu         # On Ubuntu
./symlinks arch           # On Arch (if you add an arch/ directory)
```

## Symlink Management

This dotfiles setup uses a powerful `symlinks` script that replaces GNU Stow entirely:

### Shared Configuration Management

```bash
# Link shared/ to all platform directories (macos/, wsl/, ubuntu/, etc.)
./symlinks shared

# Remove shared symlinks from platform directories  
./symlinks shared unlink

# Show shared symlinks in platform directories
./symlinks shared show
```

### Platform Configuration Management

```bash
# Link platform directory to $HOME
./symlinks macos                    # Link macos/ → $HOME
./symlinks wsl                      # Link wsl/ → $HOME  
./symlinks ubuntu                   # Link ubuntu/ → $HOME

# Remove platform symlinks from $HOME
./symlinks macos unlink
./symlinks wsl unlink

# Show platform symlinks in $HOME
./symlinks macos show
./symlinks wsl show
```

### Key Features

- **Auto-Discovery**: Automatically finds all platform directories (no hardcoding)
- **Expandable**: Adding a new platform (like `arch/`) automatically works
- **Safe Operations**: Uses `ln -sf` to overwrite safely
- **Targeted Removal**: Only removes symlinks pointing to the correct source
- **Performance Optimized**: Efficient directory scanning with depth limits

## Required Dependencies

Before installing, ensure you have these dependencies:

**Core Tools:** zsh, git, Nerd Font\
**Enhanced CLI:** zoxide, fzf, fd, eza, bat, ripgrep, delta\
**ZSH Plugins:** zsh-syntax-highlighting, git-open\
**Optional:** yazi, tmux, nvim, gh

## Manual Setup

### Legacy Symlink Management

The configuration uses a dynamic symlink system that automatically discovers all files in `shared/` and creates corresponding symlinks in platform directories using `ln -sf`:

```bash
# Create symlinks for all files in shared/ to both macos/ and wsl/
./setup-symlinks.sh create

# Show current symlink status
./setup-symlinks.sh show

# Remove all symlinks from platform directories
./setup-symlinks.sh remove

# Recreate all symlinks (remove and create)
./setup-symlinks.sh recreate
```

The script automatically:

- Finds all files in `shared/` directory structure
- Creates corresponding directory structure in `macos/` and `wsl/`
- Uses `ln -sf` to create symlinks for each file
- Handles any future additions to `shared/` automatically

### Adding New Shared Files

To add new shared configuration:

1. Place files in the appropriate `shared/` subdirectory
1. Run `./setup-symlinks.sh recreate` to update all symlinks

The script will automatically detect and symlink any new files.

### Yazi Themes

```bash
ya pkg add BennyOe/tokyo-night
ya pkg add dangooddd/kanagawa
ya pkg add bennyyip/gruvbox-dark
ya pkg add kmlupreti/ayu-dark
ya pkg add Chromium-3-Oxide/everforest-medium
ya pkg add gosxrgxx/flexoki-dark
```

## macOS Installation

### Install Dependencies (macOS)

```bash
# Core tools
brew install zsh git stow

# Enhanced CLI tools  
brew install zoxide fzf fd eza bat ripgrep git-delta

# GNU coreutils (for enhanced compatibility)
brew install coreutils gnu-sed gnu-tar grep

# ZSH plugins
brew install zsh-syntax-highlighting

# Optional tools
brew install yazi tmux neovim gh
```

### Install Nerd Font (macOS)

Download and install a Nerd Font from [nerdfonts.com](https://www.nerdfonts.com/). Configure your terminal to use it.

### Set zsh as default shell (macOS)

```bash
chsh -s $(which zsh)
```

### Install git-open plugin (macOS)

```bash
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
chmod +x ~/.config/zsh/plugins/git-open/git-open
```

### Clone dotfiles and install (macOS)

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
stow macos
# Handle any conflicting files by backing them up first
```

## Neovim Lanuage Servers

```bash
brew install lua-language-server

```

## Installing in WSL (Ubuntu)

Edit `/etc/zsh/zshenv` with `export ZSHDOTDIR="$HOME/.config/zsh"`

### System Installs

```bash
sudo apt install ripgrep tmux nvim stow fd-find xclip git-delta zsh git luarocks bat zsh-syntax-highlighting
# bat installed as batcat
ln -s /usr/bin/batcat ~/.local/bin/bat
# stuff for yazi
sudo apt install ffmpeg 7zip jq poppler-utils imagemagick chafa
# for fd need to make a symlink
ln -s $(which fdfind) ~/.local/bin/fd
```

### Install Enhanced CLI Tools

```bash
# Install Rust for cargo-based tools
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Install via cargo
cargo install zoxide eza
```

#### fzf needs to be installed and updated manually

1. Download the latest `.zip` release from github and extract
1. Go must be installed, download the linux 386 or whatever `.tar.gz` archive
   `sudo rm -rf /usr/local/go`
   `sudo tar -C /usr/local -xzf go1.25.2.linux-386.tar.gz`
1. Make sure that go is in the path
   `export PATH=$PATH:/usr/local/go/bin`
1. cd into fzf unzipped directory and `make` then `sudo make install`
1. If it does not install right `sudo cp -f target/fzf-linux_amd64 /bin/fzf`

#### yazi has to be installed manually

1. Use rust toolchain to build

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update
git clone https://github.com/sxyazi/yazi.git
cd yazi
cargo build --release --locked
sudo mv target/release/yazi target/release/ya /usr/local/bin
# !!! Important !!!
# Must now install yazi from snap, yazi is broken from cargo
# but cargo needed to get ya to install the themes
sudo snap install yazi --classic
```

Install imagemagick from source:
<https://imagemagick.org/script/install-source.php>

#### LazyGit has to be installed manually

```bash
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | \grep -Po '"tag_name": *"v\K[^"]*')
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz lazygit
sudo install lazygit -D -t /usr/local/bin/
```

### Set zsh as default shell (WSL)

`chsh -s $(which zsh)`

### Install ZSH Plugins

```bash
# Try package manager first
sudo apt install zsh-syntax-highlighting gh

# If zsh-syntax-highlighting not available, install manually
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.config/zsh/plugins/zsh-syntax-highlighting

# Install git-open manually (cross-platform compatibility)
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
chmod +x ~/.config/zsh/plugins/git-open/git-open
```

```bash
# Important: Must install nodejs and npm from `nvm` to get a recent version
# Copy install script locally if no rawgithubusercontent available
# otherwise all npm will be installed in Windows and be slow!
cargo install --locked tree-sitter-cli
cargo install stylua
uv tool install ruff
uv tool install mypy
uv tool install mdformat
uv tool install basedpyright
uv tool install sqlfluff
uv tool install codespell
npm install -g markdownlint-cli
npm install -g bash-language-server
npm install -g prettier
npm install -g @fsouza/prettierd
npm install -g vscode-langservers-extracted
npm install -g typescript-language-server typescript
npm install -g yaml-language-server
go install golang.org/x/tools/gopls@latest
go install github.com/sqls-server/sqls@latest

```

### General Intall Instructions for Binary

```bash
# Get .tar.gz or .zip from Binary Releases
# Download to ~/installs
mkdir program-name
tar xf program-name.tar.gz --directory program-name
mv program-name ~/.local/opt/
ln -s ~/.local/opt/program-name/bin/program ~/.local/bin/program
```

### Language Servers for Neovim

<https://github.com/LuaLS/lua-language-server/releases>

#### Docker Language Server

```bash
# requires gcc compiler for go
sudo apt install gcc-multilib
go install github.com/docker/docker-language-server/cmd/docker-language-server@latest
```

### Clone dotfiles and install (WSL)

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

### Set Up Clipboard for Windows Integration

Use the clipboard info in neovim options.
Download `win32yank.exe` the 64 bit version!
Put in `/usr/local/bin/win32yank.exe` on WSL
make sure to `chmod +x /usr/local/bin/win32yank.exe`

## Arch Linux Installation

### Install Dependencies (Arch Linux)

```bash
# Core tools
sudo pacman -S zsh git stow

# Enhanced CLI tools
sudo pacman -S zoxide fzf fd eza bat ripgrep git-delta

# ZSH plugins
sudo pacman -S zsh-syntax-highlighting

# Optional tools  
sudo pacman -S yazi tmux neovim github-cli
```

### Install Nerd Font (Arch Linux)

```bash
sudo pacman -S ttf-firacode-nerd
# Or install manually from nerdfonts.com
```

### Set zsh as default shell (Arch Linux)

```bash
chsh -s $(which zsh)
```

### Install git-open plugin (Arch Linux)

```bash
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
chmod +x ~/.config/zsh/plugins/git-open/git-open
```

### Clone dotfiles and install (Arch Linux)

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
stow arch  # or create arch-specific directory if needed
# Handle any conflicting files by backing them up first
```

## Features

### Custom Prompt

- **Git status with Nerd Font icons**: Branch, modified files, staged files, etc.
- **Virtual environment display**: Shows active Python venv
- **Smart user info**: Different colors for SSH sessions and root
- **Remote status**: Shows commits ahead/behind origin
- **AWS context**: Displays profile, region, and credential expiration time

### Smart Navigation

- **zoxide integration**: `z` command for smart directory jumping
- **Enhanced aliases**: `..`, `...`, `dots`, `dl`, `dt` all use smart navigation

### Plugin System

The .zshrc configuration automatically detects and loads plugins installed in standard locations:

- **zsh-syntax-highlighting**: Installed via package managers
- **git-open**: Manual installation to ~/.local/bin with executable permissions
- **colored-man-pages**: Activated via environment variables

Plugins are sourced automatically if detected, with graceful fallback handling.

### Enhanced Commands

- **fzf integration**: Fuzzy finding for files, directories, command history
- **fd + fzf**: Fast file finding with preview
- **eza + bat**: Enhanced ls and cat with syntax highlighting
- **git-open**: Open repository in browser from command line

### Cross-Platform Compatibility

- **Automatic detection**: macOS vs Linux differences handled automatically
- **Plugin management**: Hybrid approach using package managers when available
- **Path management**: GNU coreutils on macOS, native tools on Linux

## AWS Prompt Integration

The custom prompt includes intelligent AWS context display inspired by Starship's AWS module. The prompt automatically shows:

### AWS Information Displayed

- **☁️ Profile**: Current AWS profile (`$AWS_PROFILE`)
- **🌍 Region**: Current AWS region (`$AWS_REGION` or `$AWS_DEFAULT_REGION`)
- **⏰ Expiration**: Time remaining on temporary credentials

### Supported AWS Tools

The prompt detects and displays credential expiration from:

- **aws-vault**: Reads `$AWS_SESSION_EXPIRATION` environment variable
- **AWSume**: Reads `$AWSUME_EXPIRATION` environment variable
- **Manual export**: Any tool that sets these standard variables

### Display Examples

```bash
# Profile and region only
☁️ production@us-east-1

# With credential expiration
☁️ production@us-east-1 [2h15m]

# Expired credentials (shown in red)
☁️ production@us-east-1 [EXPIRED]
```

### Usage

The AWS prompt appears automatically when AWS environment variables are detected:

```bash
# Set profile and region
export AWS_PROFILE=production
export AWS_REGION=us-east-1

# For aws-vault users
aws-vault exec production -- zsh

# For AWSume users  
awsume production
```

The prompt hides completely when no AWS context is active, keeping your prompt clean.

## Troubleshooting

### Nerd Font icons not displaying

- Ensure your terminal is configured to use a Nerd Font
- Test with: `echo -e "\ue0a0 \uf067 \uf059"`
- Popular choices: FiraCode Nerd Font, JetBrainsMono Nerd Font

### Command not found errors

- Verify all required dependencies are installed
- Check that tools are in your PATH: `which zoxide fzf fd eza bat`
- Restart terminal after installation

### zsh-syntax-highlighting not working

- Install via package manager or manually to `~/.config/zsh/plugins/`
- Plugin loads automatically based on detection
- Restart terminal to see syntax highlighting

### Ubuntu fd command issues

- Ubuntu packages `fd` as `fdfind`
- Create symlink: `ln -s $(which fdfind) ~/.local/bin/fd`
- Ensure `~/.local/bin` is in your PATH
