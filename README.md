# Dotfiles

Modern, cross-platform dotfiles configuration featuring:

- Standalone zsh setup with custom prompt and Nerd Font icons
- Smart directory navigation with zoxide  
- Enhanced command-line tools (fzf, fd, eza, bat, yazi)
- Cross-platform compatibility (macOS, Ubuntu WSL, Arch Linux)

## Required Dependencies

Before installing, ensure you have these dependencies:

**Core Tools:** zsh, git, stow, Nerd Font  
**Enhanced CLI:** zoxide, fzf, fd, eza, bat, ripgrep, delta  
**ZSH Plugins:** zsh-syntax-highlighting, git-open  
**Optional:** yazi, tmux, nvim, gh

## General Setup

### Copy shared config to platform-specific directories

```bash
cp -r ~/dotfiles/shared/. ~/dotfiles/macos/
cp -r ~/dotfiles/shared/. ~/dotfiles/wsl/
```

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

### Install Dependencies

```bash
# Core tools
brew install zsh git stow

# Enhanced CLI tools  
brew install zoxide fzf fd eza bat ripgrep git-delta

# ZSH plugins
brew install zsh-syntax-highlighting

# Optional tools
brew install yazi tmux neovim gh
```

### Install Nerd Font

Download and install a Nerd Font from [nerdfonts.com](https://www.nerdfonts.com/). Configure your terminal to use it.

### Set zsh as default shell

```bash
chsh -s $(which zsh)
```

### Install git-open plugin

```bash
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
```

### Clone dotfiles and install

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
stow macos
# Handle any conflicting files by backing them up first
```

## Installing in WSL (Ubuntu)

Edit `/etc/zsh/zshenv` with `export ZSHDOTDIR="$HOME/.config/zsh"`

### System Installs

```bash
sudo apt install ripgrep tmux nvim stow fd-find xclip git-delta zsh git
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
cargo install zoxide eza bat
```

#### fzf needs to be installed and updated manually

1. Download the latest `.zip` release from github and extract
2. Go must be installed, download the linux 386 or whatever `.tar.gz` archive
   `sudo rm -rf /usr/local/go`
   `sudo tar -C /usr/local -xzf go1.25.2.linux-386.tar.gz`
3. Make sure that go is in the path
   `export PATH=$PATH:/usr/local/go/bin`
4. cd into fzf unzipped directory and `make` then `sudo make install`
5. If it does not install right `sudo cp -f target/fzf-linux_amd64 /bin/fzf`

#### yazi has to be installed manually

1. Use rust toolchain to build

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update
git clone https://github.com/sxyazi/yazi.git
cd yazi
cargo build --release --locked
sudo mv target/release/yazi target/release/ya /usr/local/bin
```

Install imagemagick from source:
<https://imagemagick.org/script/install-source.php>

### Set zsh as default shell

`chsh -s $(which zsh)`

### Install ZSH Plugins

```bash
# Try package manager first
sudo apt install zsh-syntax-highlighting

# If not available, install manually
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.config/zsh/plugins/zsh-syntax-highlighting
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
```

### Clone dotfiles and install

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
stow wsl
# delete or move any conflicting files
```

## Arch Linux Installation

### Install Dependencies

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

### Install Nerd Font

```bash
sudo pacman -S ttf-firacode-nerd
# Or install manually from nerdfonts.com
```

### Set zsh as default shell

```bash
chsh -s $(which zsh)
```

### Install git-open plugin

```bash
mkdir -p ~/.config/zsh/plugins
git clone https://github.com/paulirish/git-open.git ~/.config/zsh/plugins/git-open
```

### Clone dotfiles and install

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

### Smart Navigation

- **zoxide integration**: `z` command for smart directory jumping
- **Enhanced aliases**: `..`, `...`, `dots`, `dl`, `dt` all use smart navigation

### Enhanced Commands

- **fzf integration**: Fuzzy finding for files, directories, command history
- **fd + fzf**: Fast file finding with preview
- **eza + bat**: Enhanced ls and cat with syntax highlighting
- **git-open**: Open repository in browser from command line

### Cross-Platform Compatibility

- **Automatic detection**: macOS vs Linux differences handled automatically
- **Plugin management**: Hybrid approach using package managers when available
- **Path management**: GNU coreutils on macOS, native tools on Linux

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
