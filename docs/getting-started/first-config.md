# First Configuration

Post-installation configuration.

## Git Identity

```sh
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Platform-specific git configs are in `macos/.gitconfig` and `wsl/.gitconfig`.

## Themes

List available themes:

```sh
theme-sync favorites
```

Apply a theme:

```sh
theme-sync apply base16-gruvbox-dark-hard
```

Syncs colors across tmux, bat, fzf, and shell.

For Ghostty (separate system):

```sh
ghostty-theme "Rose Pine"
```

## Tools

```sh
tools list              # List all installed tools
tools show bat          # Detailed info about a tool
tools search git        # Find git-related tools
tools random            # Discover random tool
```

## Shell Customization

**Aliases**: Edit `platforms/common/.config/zsh/aliases.zsh`

**Functions**: Edit `platforms/{platform}/.config/zsh/functions.zsh` (platform-specific)

Reload: `source ~/.zshrc`

## Neovim

First launch installs plugins automatically (lazy.nvim).

LSPs are pre-configured. Check installed:

```sh
npm list -g --depth=0 | grep language-server
```

Choose colorscheme in Neovim: `:Telescope colorscheme`

## Tmux

**Prefix**: `Ctrl + Space`

Common commands:

```sh
Ctrl+Space c        # New window
Ctrl+Space |        # Split vertical
Ctrl+Space -        # Split horizontal
Ctrl+Space h/j/k/l  # Navigate panes
```

Reload config: `Ctrl+Space r`

## Verification

```sh
# Check tools
bat --version
eza --version
rg --version

# Check git
git config user.name
git config user.email

# Check shell
echo $SHELL                    # Should be /bin/zsh
echo $PATH | grep ".local/bin" # Should find it

# Check neovim
nvim --version                 # Should be 0.11+
```

In Neovim: `:checkhealth` and `:LspInfo`

## Task Commands

```sh
task --list         # Show all tasks
task update         # Update all packages
task verify         # Verify installation
```

See [Architecture Overview](../architecture/index.md) for how everything works.
