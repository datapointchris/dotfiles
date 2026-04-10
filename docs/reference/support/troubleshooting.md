# Troubleshooting

Common issues and solutions.

## Command Not Found

!!! warning "Symptom"
    Tool installed but command not found

!!! info "Check PATH"
    ```sh
    echo $PATH | tr ':' '\n'
    ```

    Should include:

    - `~/.local/bin`
    - `~/.local/share/nvm/versions/node/<version>/bin` (if using nvm)
    - `/usr/local/bin` or `/opt/homebrew/bin` (macOS)

!!! tip "Fix: Reload shell"
    ```sh
    source ~/.config/zsh/.zshrc
    # or
    exec zsh
    ```

## Neovim Issues

!!! warning "Plugins won't load"
    ```sh
    nvim -c "Lazy sync" -c "qa"    # Force sync
    rm -rf ~/.local/share/nvim/lazy/  # Clear cache
    ```

!!! warning "LSP not working"
    ```sh
    :LspInfo                # Check attached servers
    :checkhealth vim.lsp    # Run diagnostics
    ```

!!! warning "Version too old"
    ```sh
    nvim --version          # Should be 0.11+
    brew upgrade neovim     # macOS
    ```

## Symlink Issues

!!! warning "Config file not updating"
    ```sh
    ls -la ~/.config/zsh/.zshrc  # Check symlink
    symlinks relink macos        # Recreate symlinks
    ```

## Theme Issues

!!! warning "Theme not applying"
    ```sh
    theme current           # Check current theme
    theme verify            # Check theme system
    theme apply <name>      # Apply theme directly
    ```

!!! warning "Tmux colors wrong"
    ```sh
    # In tmux
    Ctrl+Space r            # Reload tmux config
    ```

## Git Issues

!!! tip "Git identity not set"
    ```sh
    git config --global user.name "Your Name"
    git config --global user.email "your@email.com"
    ```

!!! tip "Credential helper not working (macOS)"
    ```sh
    git config --global credential.helper osxkeychain
    ```

## Package Manager Issues

!!! warning "Homebrew slow/hanging (macOS)"
    ```sh
    brew update             # Update package lists
    brew doctor             # Check for issues
    brew cleanup            # Clean old versions
    ```

!!! warning "apt package not found (Ubuntu)"
    ```sh
    sudo apt update         # Update package lists
    ```

    Some tools need cargo install or manual installation on Ubuntu. See [Platform Differences](../platforms/differences.md).

## WSL-Specific

!!! info "ZDOTDIR not working"
    Check `/etc/zshenv` (macOS) or `/etc/zsh/zshenv` (Ubuntu/WSL):

    ```sh
    cat /etc/zshenv
    ```

    Should contain:

    ```sh
    export ZDOTDIR="$HOME/.config/zsh"
    ```

## Still Having Issues?

Check git history (`git log --oneline`) for recent changes that may have introduced issues.
