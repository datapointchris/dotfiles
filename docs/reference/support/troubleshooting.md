# Troubleshooting

Common issues and solutions.

## Command Not Found

**Symptom**: Tool installed but command not found

**Check PATH**:

```sh
echo $PATH | tr ':' '\n'
```

Should include:

- `~/.local/bin`
- `~/.config/nvm/versions/node/<version>/bin` (if using nvm)
- `/usr/local/bin` or `/opt/homebrew/bin` (macOS)

**Fix**: Reload shell

```sh
source ~/.config/zsh/.zshrc
# or
exec zsh
```

## Neovim Issues

**Plugins won't load**:

```sh
nvim -c "Lazy sync" -c "qa"    # Force sync
rm -rf ~/.local/share/nvim/lazy/  # Clear cache
```

**LSP not working**:

```sh
:LspInfo                # Check attached servers
:checkhealth vim.lsp    # Run diagnostics
```

**Version too old**:

```sh
nvim --version          # Should be 0.11+
brew upgrade neovim     # macOS
```

## Symlink Issues

**Config file not updating**:

```sh
ls -la ~/.config/zsh/.zshrc  # Check symlink
symlinks relink macos        # Recreate symlinks
```

## Theme Issues

**Theme not applying**:

```sh
theme-sync current      # Check current theme
tinty apply <theme>     # Try direct tinty command
```

**Tmux colors wrong**:

```sh
# In tmux
Ctrl+Space r            # Reload tmux config
```

## Git Issues

**Git identity not set**:

```sh
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

**Credential helper not working** (macOS):

```sh
git config --global credential.helper osxkeychain
```

## Package Manager Issues

**Homebrew slow/hanging** (macOS):

```sh
brew update             # Update package lists
brew doctor             # Check for issues
brew cleanup            # Clean old versions
```

**apt package not found** (Ubuntu):

```sh
sudo apt update         # Update package lists
```

Some tools need cargo install or manual installation on Ubuntu. See [Platform Differences](platforms.md).

## WSL-Specific

**ZSHDOTDIR not working**:

Check `/etc/zsh/zshenv`:

```sh
cat /etc/zsh/zshenv
```

Should contain:

```sh
export ZSHDOTDIR="$HOME/.config/zsh"
```

**Binary symlinks missing** (bat, fd):

```sh
ln -sf /usr/bin/batcat ~/.local/bin/bat
ln -sf /usr/bin/fdfind ~/.local/bin/fd
```

## Still Having Issues?

Check recent [changelog entries](../changelog.md) for known issues and solutions.
