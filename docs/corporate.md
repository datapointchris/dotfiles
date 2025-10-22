# Corporate Environment Setup Guide

This guide provides specific solutions for using this Neovim configuration in corporate environments where certain domains or package managers are blocked.

## Common Corporate Restrictions

- `raw.githubusercontent.com` blocked (breaks Mason)
- `registry.npmjs.org` restricted (npm issues)
- Proxy required for external connections
- Limited admin/sudo access
- Package managers restricted

## Solution: Native LSP (Recommended)

**Good news!** This configuration already uses **native Neovim LSP** which bypasses most corporate restrictions:

✅ **No Mason dependency** - Install servers manually  
✅ **No external registries** - Direct tool installation  
✅ **System package managers** - Use approved tools  
✅ **Offline capable** - Works without constant internet  

## Quick Start for Corporate

### 1. Install Core Dependencies

```bash
# macOS (via approved Homebrew)
brew install neovim git node python

# Linux (via apt/yum)
sudo apt install neovim git nodejs npm python3-pip
```

### 2. Run Corporate Installation Script

```bash
# From dotfiles root
./scripts/install-lsp-corporate.sh
```

This script installs language servers using system package managers instead of Mason.

### 3. Local Mirror Registry

There are **two approaches** for using a local mirror:

#### Option A: Manual Registry Download (Recommended)

Download the registry manually and place it in Mason's data directory:

```bash
# Step 1: Download on a machine with internet access
git clone https://github.com/mason-org/mason-registry.git
tar -czf mason-registry.tar.gz mason-registry/

# Step 2: Transfer to restricted machine
# Copy mason-registry.tar.gz to your work machine

# Step 3: Extract to Mason's data directory
cd ~/.local/share/nvim/mason-registry
tar -xzf /path/to/mason-registry.tar.gz --strip-components=1

# Step 4: No configuration changes needed!
# Mason will automatically use the local registry
```

#### Option B: Custom Registry Path

Set up a local mirror and configure Mason to use it:

```lua
-- In your Mason configuration
require("mason").setup({
  registries = {
    "file:/home/username/mason-local/mason-registry",  -- Local mirror first
    "github:mason-org/mason-registry",                 -- Fallback to GitHub
  },
})
```

To set up the custom path:

```bash
# On a machine with internet access:
git clone https://github.com/mason-org/mason-registry.git ~/mason-local/mason-registry

# Or if you need to transfer it:
tar -czf mason-registry.tar.gz mason-registry/
# Transfer and extract to ~/mason-local/mason-registry
```

**Note:** Option A is simpler because Mason automatically looks in its data directory first, so no configuration changes are needed!

## Manual Language Server Installation

### Essential Servers (Work Priority)

#### 1. TypeScript/JavaScript

```bash
# Via npm (most common in corporate)
npm install -g typescript typescript-language-server

# Verify
typescript-language-server --version
```

#### 2. Python

```bash
# Via pip (user install, no sudo needed)
pip install --user basedpyright ruff

# Verify
basedpyright --version
ruff --version
```

#### 3. Lua (for Neovim config)

```bash
# macOS
brew install lua-language-server

# Linux - manual download
wget https://github.com/LuaLS/lua-language-server/releases/latest/download/lua-language-server-3.x.x-linux-x64.tar.gz
tar -xzf lua-language-server-3.x.x-linux-x64.tar.gz -C ~/.local/share/lua-language-server
echo 'export PATH="$HOME/.local/share/lua-language-server/bin:$PATH"' >> ~/.zshrc
```

#### 4. Go (if used)

```bash
# Via go install (if Go is allowed)
go install golang.org/x/tools/gopls@latest

# Or download binary manually
```

#### 5. JSON/HTML/CSS

```bash
# Single package for multiple servers
npm install -g vscode-langservers-extracted

# Provides: html-languageserver, css-languageserver, json-languageserver, eslint-languageserver
```

### Additional Servers (As Needed)

```bash
# Bash
npm install -g bash-language-server

# Docker
npm install -g dockerfile-language-server-nodejs

# Markdown
brew install marksman  # macOS
# or download from GitHub releases

# TOML
cargo install taplo-cli --locked  # if Rust available

# SQL
npm install -g sql-language-server

# Vim
npm install -g vim-language-server
```

## Offline Installation Methods

### 1. Download Packages at Home

```bash
# Create offline package cache
mkdir ~/offline-packages

# Download npm packages for offline install
npm pack typescript typescript-language-server
npm pack bash-language-server
npm pack vscode-langservers-extracted
# ... etc

# At work: install from local files
npm install -g ./typescript-x.x.x.tgz
npm install -g ./typescript-language-server-x.x.x.tgz
```

### 2. Use Company Package Mirrors

```bash
# Configure npm to use company mirror
npm config set registry http://npm.company.com/

# Configure pip to use company mirror
pip config set global.index-url http://pypi.company.com/simple/
```

### 3. Manual Binary Downloads

Many language servers provide pre-built binaries:

1. **Download at home** from GitHub releases
2. **Transfer via approved methods** (USB, email, etc.)
3. **Extract to user directories** (`~/.local/bin/`)
4. **Add to PATH** in shell profile

## Corporate-Friendly Configuration

### Disable External Features

```lua
-- In your Neovim config, disable features that require internet
local config = {
  -- Disable plugin auto-updates
  lazy = {
    checker = { enabled = false },  -- Don't check for updates
    change_detection = { enabled = false },
  },

  -- Disable AI features if API access blocked
  codecompanion = { enabled = false },
  copilot = { enabled = false },

  -- Use offline help/docs
  telescope = {
    defaults = {
      file_ignore_patterns = { "node_modules", ".git" },
    },
  },
}
```

### Local Documentation

```bash
# Download documentation for offline use
git clone https://github.com/neovim/neovim.git ~/docs/neovim
git clone https://github.com/mason-org/mason-registry.git ~/docs/mason-registry
```

## Troubleshooting Corporate Issues

### Issue: npm install fails

**Solution:** Configure npm registry

```bash
# Check current registry
npm config get registry

# Set to company registry
npm config set registry http://npm.company.com/

# Or use public mirror
npm config set registry https://registry.npmmirror.com/
```

### Issue: Git clone fails

**Solution:** Configure git proxy or use alternative methods

```bash
# Use HTTPS instead of SSH
git config --global url."https://github.com/".insteadOf "git@github.com:"

# Or download zip files instead of git clone
wget https://github.com/user/repo/archive/main.zip
```

### Issue: Language server binary not found

**Solution:** Check PATH and installation location

```bash
# Check PATH
echo $PATH

# Find installed binaries
which typescript-language-server
find ~ -name "*language-server*" 2>/dev/null

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### Issue: SSL certificate errors

**Solution:** Configure certificates or disable SSL verification

```bash
# For npm
npm config set strict-ssl false

# For git (not recommended, use company certificates)
git config --global http.sslverify false

# Better: add company certificate
git config --global http.sslcainfo /path/to/company-cert.pem
```

## Verification Checklist

After installation, verify everything works:

```bash
# 1. Check Neovim starts
nvim --version

# 2. Check language servers
which typescript-language-server
which basedpyright
which lua-language-server

# 3. Test in Neovim
nvim test.js
# In Neovim: :LspInfo

# 4. Check completion works
# In Neovim: <C-x><C-o> for completion

# 5. Check diagnostics
# Open file with errors, should see diagnostics
```

## Getting Help in Corporate Environment

### Internal Resources

1. **Check company wiki** for approved package managers
2. **Ask IT department** about proxy configurations
3. **Use company Slack/Teams** for developer tool discussions
4. **Check internal mirrors** for npm/pip packages

### Documentation

1. **Save offline docs** for language servers
2. **Print reference cards** for key shortcuts
3. **Use `:help` in Neovim** for built-in documentation
4. **Keep troubleshooting notes** for team sharing

## Alternative: Minimal Setup

If full setup is too complex, create a minimal corporate-friendly config:

```lua
-- minimal-corporate.lua
-- Basic Neovim with native LSP only

-- Core settings
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.expandtab = true
vim.opt.shiftwidth = 2

-- Native LSP setup (no external dependencies)
vim.api.nvim_create_autocmd('LspAttach', {
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    vim.lsp.completion.enable(true, client.id, args.buf, { autotrigger = true })
  end,
})

-- Manual server configs (no Mason needed)
vim.lsp.config.ts_ls = {
  cmd = { 'typescript-language-server', '--stdio' },
  filetypes = { 'typescript', 'javascript' },
}

vim.lsp.config.basedpyright = {
  cmd = { 'basedpyright-langserver', '--stdio' },
  filetypes = { 'python' },
}

-- Enable servers
vim.lsp.enable({ 'ts_ls', 'basedpyright' })
```

Use with: `nvim -u minimal-corporate.lua`

This provides LSP functionality with zero external dependencies!
