# Setup Guide

This guide covers initial installation and configuration of the Neovim setup.

## Prerequisites

### System Requirements

- **Neovim 0.11+** (required for native LSP features)
- **Git** (for plugin management and dotfiles)
- **Node.js** (for language servers)
- **Python 3.8+** (for Python tools)
- **Rust** (for Rust tools, optional)

### Platform-Specific Dependencies

#### macOS (Homebrew)

```bash
# Core dependencies
brew install neovim git node python rust

# Additional tools
brew install fd ripgrep fzf eza bat zoxide
```

#### Ubuntu/Linux

```bash
# Core dependencies
sudo apt update
sudo apt install neovim git nodejs npm python3 python3-pip

# Additional tools
sudo apt install fd-find ripgrep fzf
cargo install eza bat zoxide  # if Rust is available
```

## Installation

### 1. Dotfiles Setup

```bash
# Clone dotfiles repository
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Link configurations (use appropriate platform)
./symlinks shared       # Link shared configs to platform dirs
./symlinks macos        # or ./symlinks wsl
```

### 2. Neovim Plugin Installation

```bash
# Start Neovim (plugins will auto-install via Lazy.nvim)
nvim

# Wait for plugins to install, then restart
:qa
nvim
```

### 3. Language Server Installation

See the [LSP Guide](./lsp.md) for detailed language server installation instructions.

## Configuration Structure

### Core Files

- `init.lua` - Entry point, loads core modules
- `lua/core/` - Core Neovim settings and keymaps
- `lua/plugins/` - Plugin specifications for Lazy.nvim
- `lsp/` - Native LSP server configurations

### Key Configuration Files

| File | Purpose |
|------|---------|
| `lua/core/options.lua` | Neovim options and settings |
| `lua/core/keymaps.lua` | Global keymaps and bindings |
| `lua/core/lazy.lua` | Lazy.nvim plugin manager setup |
| `lsp/init.lua` | LSP coordination and setup |
| `lua/plugins/native-lsp.lua` | Native LSP plugin configuration |

## Post-Installation Steps

### 1. Verify Installation

```bash
# Check Neovim health
nvim --headless -c "checkhealth" -c "qa"

# Check LSP status
nvim -c "checkhealth vim.lsp"
```

### 2. Configure AI Integration (Optional)

If using CodeCompanion with Claude:

```bash
# Set API key
export ANTHROPIC_API_KEY="your-api-key-here"

# Add to shell profile
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
```

### 3. Configure Git Integration

```bash
# Set up git delta for diffs (recommended)
brew install git-delta  # macOS
# or sudo apt install git-delta  # Ubuntu

# Configure git to use delta
git config --global core.pager delta
git config --global interactive.diffFilter "delta --color-only"
```

## Verification Checklist

After installation, verify these features work:

- [ ] Neovim starts without errors
- [ ] Plugins are installed (check with `:Lazy`)
- [ ] LSP servers start for your languages (check with `:LspInfo`)
- [ ] Completion works with `<C-x><C-o>` or auto-trigger
- [ ] Git integration works (open a git repo and use `<leader>g` commands)
- [ ] Telescope works for file finding (`<leader>ff`)
- [ ] Theme loads correctly
- [ ] No startup errors (check with `:messages`)

## Customization

### Adding Language Servers

1. Install the language server (see [LSP Guide](./lsp.md))
2. Create config in `lsp/servername.lua`
3. Add server name to `lsp/init.lua` servers list

### Changing Themes

Edit `lua/plugins/colorschemes.lua` and set your preferred theme:

```lua
vim.cmd.colorscheme('your-theme-name')
```

### Custom Keymaps

Add to `lua/core/keymaps.lua`:

```lua
vim.keymap.set('n', '<leader>your-key>', '<cmd>YourCommand<cr>', { desc = 'Description' })
```

## Troubleshooting

See the [Troubleshooting Guide](./troubleshooting.md) for common issues and solutions.
