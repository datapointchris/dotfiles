# Troubleshooting Guide

This guide covers common issues and solutions for the Neovim configuration.

## Startup Issues

### Neovim Won't Start

#### Error: "Neovim version too old"

```bash
# Check Neovim version
nvim --version

# Should be 0.11.0 or higher
# If not, update:
brew upgrade neovim  # macOS
```

#### Error: "Failed to load init.lua"

```bash
# Check for syntax errors
nvim --headless -c "luafile ~/.config/nvim/init.lua" -c "qa"

# Start with minimal config
nvim --clean
```

#### Plugins Won't Load

```bash
# Check Lazy.nvim status
nvim -c "Lazy"

# Force plugin sync
nvim -c "Lazy sync" -c "qa"

# Clear plugin cache
rm -rf ~/.local/share/nvim/lazy/
```

## LSP Issues

### Language Servers Not Starting

#### Check Server Installation

```bash
# Verify servers are installed
which typescript-language-server
which basedpyright
which lua-language-server

# Check LSP status in Neovim
:LspInfo
:checkhealth vim.lsp
```

#### Common Installation Issues

**Node.js servers not found:**

```bash
# Check npm global path
npm config get prefix
echo $PATH

# Fix PATH if needed
export PATH="$PATH:$(npm config get prefix)/bin"
```

**Python servers not found:**

```bash
# Check pip installation location
pip show basedpyright
which basedpyright

# Install with --user if needed
pip install --user basedpyright ruff
```

#### Server Config Errors

```bash
# Test individual server config
:lua local config = dofile('/Users/chris/dotfiles/macos/.config/nvim/lsp/lua_ls.lua'); print(vim.inspect(config))

# Check for syntax errors
:luafile ~/.config/nvim/lsp/lua_ls.lua
```

### Completion Not Working

#### Native LSP Completion

```vim
" Check completion is enabled
:lua print(vim.lsp.completion.get())

" Verify omnifunc is set
:set omnifunc?
" Should show: omnifunc=v:lua.vim.lsp.omnifunc

" Manual completion trigger
<C-x><C-o>
```

#### Completion Menu Issues

```vim
" Check completeopt settings
:set completeopt?
" Should include: menu,menuone,noselect

" Reset completion
:lua vim.lsp.completion.enable(false); vim.lsp.completion.enable(true)
```

### Diagnostics Not Showing

#### Check Diagnostic Configuration

```lua
-- Check diagnostic config
:lua print(vim.inspect(vim.diagnostic.config()))

-- Reset diagnostics
:lua vim.diagnostic.reset()

-- Force refresh
:lua vim.diagnostic.show()
```

#### Signs Not Visible

```vim
" Check sign column
:set signcolumn?
" Should be: signcolumn=yes or auto

" List diagnostic signs
:sign list
```

## AI Integration Issues

### CodeCompanion Problems

#### API Key Issues

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY

# Test API connection
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     -H "anthropic-version: 2023-06-01" \
     -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
     https://api.anthropic.com/v1/messages
```

#### Chat Buffer Issues

```vim
:CodeCompanion log              " Check logs
:checkhealth codecompanion      " Health check

" Manual chat buffer open
:CodeCompanionChat
```

#### Memory Not Loading

```bash
# Check memory files
ls -la CLAUDE.md .cursorrules

# Test file permissions
cat CLAUDE.md
```

### Copilot Issues

#### Authentication

```vim
:Copilot auth                   " Authenticate
:Copilot status                 " Check status
```

#### Suggestions Not Working

```lua
-- Check Copilot configuration
:lua print(vim.inspect(require('copilot.config').get()))

-- Restart Copilot
:Copilot disable
:Copilot enable
```

## Performance Issues

### Slow Startup

#### Profile Startup Time

```bash
# Generate startup profile
nvim --startuptime startup.log

# Find slow plugins
grep -E "loading|sourcing" startup.log | sort -k2 -n
```

#### Common Slow Components

1. **Large plugin count** - Consider lazy loading
2. **Heavy LSP configs** - Optimize server settings
3. **Treesitter parsers** - Install only needed languages
4. **Large init.lua** - Split into modules

### High Memory Usage

#### Monitor Memory

```bash
# Check Neovim memory usage
ps aux | grep nvim

# LSP server memory
:lua for _, client in ipairs(vim.lsp.get_clients()) do print(client.name, client.id) end
```

#### Memory Optimization

```lua
-- Reduce LSP debounce
flags = {
  debounce_text_changes = 300,  -- Increase from 150
}

-- Limit treesitter
require('nvim-treesitter.configs').setup({
  ensure_installed = { "lua", "python", "javascript" },  -- Only essentials
})
```

### Laggy Completion

#### Completion Performance

```lua
-- Adjust completion timing
vim.opt.updatetime = 300    -- Default: 4000
vim.opt.timeoutlen = 500    -- Default: 1000
```

#### Server-Specific Issues

**TypeScript/JavaScript:**

```bash
# Clear TypeScript cache
rm -rf node_modules/.cache/
rm -rf .tsbuildinfo
```

**Python:**

```bash
# Clear Python cache
find . -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

## File and Directory Issues

### Config Files Not Found

#### Check Symlinks

```bash
# Verify symlinks are correct
ls -la ~/.config/nvim
ls -la ~/dotfiles/macos/.config/nvim

# Re-link if broken
cd ~/dotfiles
./symlinks macos unlink
./symlinks macos link
```

#### Permission Issues

```bash
# Fix permissions
chmod -R 755 ~/.config/nvim
chmod -R 644 ~/.config/nvim/**/*.lua
```

### Plugin Directory Issues

```bash
# Clear plugin data
rm -rf ~/.local/share/nvim/
rm -rf ~/.local/state/nvim/

# Restart Neovim (plugins will reinstall)
nvim
```

## Git Integration Issues

### Git Signs Not Working

```vim
" Check git status
:Git status

" Refresh git signs
:Gitsigns refresh
:Gitsigns toggle_signs
```

### Delta Integration

```bash
# Verify delta is installed
which delta

# Check git config
git config --list | grep pager
git config --list | grep delta
```

## Network Issues

### Corporate Firewall / Mason Registry Issues

#### Problem: Mason Can't Download Registry

Many corporate environments block `raw.githubusercontent.com`, preventing Mason from downloading its package registry.

**Solution 1: Configure Proxy in Mason**

```lua
### Corporate Networks

For corporate environments with restrictive firewalls or proxy requirements, see the dedicated [Corporate Environment Guide](./corporate.md) which covers:

- Mason registry blocking solutions
- Proxy configuration
- Manual language server installation
- Offline installation methods
- Alternative package sources
```

**Solution 2: Set Environment Variables**

```bash
# Add to your shell profile (.zshrc, .bashrc)
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export http_proxy=http://proxy.company.com:8080
export https_proxy=http://proxy.company.com:8080

# For npm-based language servers
npm config set proxy http://proxy.company.com:8080
npm config set https-proxy http://proxy.company.com:8080

# For git (used by Mason)
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy http://proxy.company.com:8080
```

**Solution 3: Use Alternative Registry**

```lua
-- Configure Mason to use alternative sources
require("mason").setup({
  registries = {
    "file:///path/to/local/registry",  -- Local mirror
    "github:your-company/mason-registry-mirror",  -- Company mirror
    "github:mason-org/mason-registry",  -- Fallback
  }
})
```

**Solution 4: Manual Registry Download**

```bash
# Download registry manually and place in Mason data directory
mkdir -p ~/.local/share/nvim/mason/registries/github__mason-org__mason-registry
cd ~/.local/share/nvim/mason/registries/github__mason-org__mason-registry

# Download via corporate-approved method (VPN, wget with proxy, etc.)
git clone https://github.com/mason-org/mason-registry.git .
```

**Solution 5: Switch to Native LSP (Recommended)**

This configuration already uses **native LSP** which bypasses Mason entirely:

1. **Manual Installation**: Install language servers using system package managers
2. **No Registry Dependency**: No need for Mason's registry downloads
3. **Better Control**: Direct control over versions and sources

```bash
# Install servers manually instead of via Mason
brew install lua-language-server typescript-language-server
npm install -g bash-language-server
pip install basedpyright ruff
```

See the [LSP Guide](./lsp.md) for complete manual installation instructions.

### Slow Plugin Updates

```bash
# Check git configuration
git config --global http.postBuffer 524288000
git config --global http.maxRequestBuffer 100M

# Use SSH instead of HTTPS
git config --global url."git@github.com:".insteadOf "https://github.com/"
```

### Proxy Configuration

```bash
# Set proxy for git
git config --global http.proxy http://proxy:port
git config --global https.proxy https://proxy:port

# Set proxy for npm
npm config set proxy http://proxy:port
npm config set https-proxy https://proxy:port
```

## Recovery Procedures

### Complete Reset

```bash
# Backup current config
mv ~/.config/nvim ~/.config/nvim.backup

# Fresh install
cd ~/dotfiles
./symlinks macos unlink
./symlinks shared unlink
git pull origin main
./symlinks shared link
./symlinks macos link

# Start Neovim (fresh install)
nvim
```

### Minimal Config Test

Create `~/.config/nvim/init-minimal.lua`:

```lua
-- Minimal config for testing
vim.opt.number = true
vim.opt.relativenumber = true

-- Test a single plugin
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({ "git", "clone", "https://github.com/folke/lazy.nvim.git", lazypath })
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
  "nvim-lua/plenary.nvim",  -- Test basic plugin
})
```

Start with: `nvim -u ~/.config/nvim/init-minimal.lua`

## Debug Commands

### Useful Debug Commands

```vim
:messages                       " Show all messages
:checkhealth                    " General health check
:checkhealth vim.lsp            " LSP health check
:LspInfo                        " Active LSP clients
:Lazy                          " Plugin manager status
:lua =vim.lsp.get_clients()     " List LSP clients
:lua =vim.diagnostic.get()      " Show diagnostics
:set ft?                       " Check filetype
:set rtp?                      " Check runtime path
```

### Log Files

```bash
# LSP logs
tail -f ~/.local/state/nvim/lsp.log

# Plugin logs (if enabled)
tail -f ~/.local/state/nvim/lazy.log

# System logs (macOS)
tail -f /var/log/system.log | grep nvim
```

## Getting Help

### Before Asking for Help

1. **Check health**: `:checkhealth`
2. **Test minimal config**: Use init-minimal.lua
3. **Search issues**: Check plugin repositories
4. **Read error messages**: Use `:messages`
5. **Check logs**: Review relevant log files

### Providing Debug Information

When seeking help, include:

```bash
# System information
neovim --version
uname -a

# Config location
echo $XDG_CONFIG_HOME
ls -la ~/.config/nvim

# Plugin status
nvim -c "Lazy" -c "qa"

# LSP status
nvim -c "checkhealth vim.lsp" -c "qa"

# Error messages
nvim -c "messages" -c "qa"
```
