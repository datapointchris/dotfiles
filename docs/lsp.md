# LSP Configuration Guide

This guide covers the native LSP setup, language server installation, and troubleshooting.

## Architecture Overview

This configuration uses **Neovim 0.11+ native LSP** without Mason or nvim-lspconfig:

- **`vim.lsp.config()`** - Defines server configurations
- **`vim.lsp.enable()`** - Enables automatic server activation
- **`vim.lsp.completion.enable()`** - Enables native completion
- **Individual server configs** in `/lsp/` directory

## Native LSP Benefits

- **Faster startup** - No plugin overhead
- **Automatic server discovery** - Configs loaded from runtimepath
- **Built-in completion** - No nvim-cmp dependency
- **Better integration** - Direct Neovim core functionality
- **Simpler debugging** - Fewer abstraction layers

## Language Server Installation

### Quick Install (macOS)

```bash
# Install most servers with Homebrew/npm
./scripts/install-lsp-servers.sh  # If available
```

### Manual Installation

#### Essential Servers

```bash
# Python
brew install basedpyright ruff  # or pip install basedpyright ruff

# JavaScript/TypeScript
npm install -g typescript typescript-language-server
npm install -g vscode-langservers-extracted  # html, css, json, eslint

# Lua
brew install lua-language-server

# Go
brew install gopls

# Rust
rustup component add rust-analyzer

# Bash
brew install bash-language-server
```

#### Additional Servers

```bash
# Docker
npm install -g dockerfile-language-server-nodejs
npm install -g @microsoft/compose-language-service

# Infrastructure
brew install terraform-ls tflint

# Markdown
brew install marksman

# TOML
brew install taplo

# SQL
npm install -g sql-language-server

# Vim
npm install -g vim-language-server
```

### Ubuntu Installation

For Ubuntu-specific installation commands, see the original LSP_INSTALLATION.md content.

## Configuration Structure

### LSP Directory (`/lsp/`)

```text
lsp/
├── init.lua              # Central coordination
├── basedpyright.lua      # Python type checking
├── ruff.lua             # Python linting/formatting
├── ts_ls.lua            # TypeScript/JavaScript
├── lua_ls.lua           # Lua
├── gopls.lua            # Go
├── rust_analyzer.lua    # Rust
└── ...                  # Other servers
```

### Server Configuration Pattern

Each server config follows this pattern:

```lua
-- lsp/servername.lua
return {
  cmd = { 'server-command', '--stdio' },
  filetypes = { 'filetype1', 'filetype2' },
  root_markers = { 'package.json', '.git' },
  settings = {
    -- Server-specific settings
  },
}
```

### Central Setup (`lsp/init.lua`)

Handles:

- Server list management
- Auto-completion setup
- Diagnostic configuration
- Format-on-save setup
- Error handling

## Key Features

### Native Keymaps (Provided by Neovim 0.11+)

- `gra` - Code actions
- `gri` - Go to implementation  
- `grn` - Rename symbol
- `grr` - Find references
- `grt` - Go to type definition
- `gO` - Document symbols
- `K` - Hover documentation
- `<C-S>` (Insert) - Signature help

### Auto-Completion

- **Auto-trigger** - Completion appears as you type
- **Accept**: `<C-y>` to accept completion
- **Dismiss**: `<C-e>` to dismiss
- **Manual trigger**: `<C-x><C-o>` for omnifunc

### Diagnostics

- **Signs** in sign column for errors/warnings
- **Virtual text** showing error messages inline
- **Navigation**: `]d` next diagnostic, `[d` previous
- **Quickfix**: `<leader>q` to populate quickfix list

### Format-on-Save

Enabled for these servers:

- `basedpyright`, `ruff` (Python)
- `gopls` (Go)
- `rust_analyzer` (Rust)
- `lua_ls` (Lua)
- `ts_ls` (TypeScript/JavaScript)

## Server Capabilities

| Server | Diagnostics | Formatting | Completion | Go-to-def | References |
|--------|-------------|------------|------------|-----------|------------|
| basedpyright | ✅ | ❌ | ✅ | ✅ | ✅ |
| ruff | ✅ | ✅ | ❌ | ❌ | ❌ |
| ts_ls | ✅ | ✅ | ✅ | ✅ | ✅ |
| gopls | ✅ | ✅ | ✅ | ✅ | ✅ |
| rust_analyzer | ✅ | ✅ | ✅ | ✅ | ✅ |
| lua_ls | ✅ | ✅ | ✅ | ✅ | ✅ |
| eslint | ✅ | ✅ | ❌ | ❌ | ❌ |

## Troubleshooting

### Common Issues

#### Server Not Starting

```bash
# Check if server is installed
which typescript-language-server
which basedpyright

# Check Neovim LSP status
:LspInfo
:checkhealth vim.lsp
```

#### Completion Not Working

```bash
# Check completion is enabled
:lua print(vim.lsp.completion.get())

# Verify omnifunc is set
:set omnifunc?

# Should show: omnifunc=v:lua.vim.lsp.omnifunc
```

#### Diagnostics Not Showing

```lua
-- Check diagnostic configuration
:lua print(vim.inspect(vim.diagnostic.config()))

-- Force diagnostic refresh
:lua vim.diagnostic.reset()
```

#### Config Not Loading

```bash
# Test individual server config
:lua local config = dofile('/path/to/lsp/servername.lua'); print(vim.inspect(config))

# Check for syntax errors
:luafile /path/to/lsp/servername.lua
```

### Debug Commands

```vim
:LspInfo                    " Show attached clients
:checkhealth vim.lsp        " LSP health check
:lua =vim.lsp.get_clients() " List active clients
:messages                   " Show startup messages
```

### Log Files

```bash
# LSP logs
tail -f ~/.local/state/nvim/lsp.log

# Neovim startup issues
nvim --startuptime startup.log
```

## Adding New Language Servers

### 1. Install the Server

```bash
# Example: Installing a new server
npm install -g some-language-server
```

### 2. Create Configuration

```lua
-- lsp/newserver.lua
return {
  cmd = { 'new-language-server', '--stdio' },
  filetypes = { 'newlang' },
  root_markers = { 'project.toml', '.git' },
  settings = {
    newServer = {
      enable = true,
    },
  },
}
```

### 3. Add to Server List

```lua
-- In lsp/init.lua, add to servers list
local servers = {
  -- existing servers...
  'newserver',
}
```

### 4. Test Configuration

```bash
# Start Neovim with a file of the new type
nvim test.newlang

# Check LSP status
:LspInfo
```

## Performance Optimization

### Reduce Startup Time

- **Native LSP** is already optimized
- **Lazy loading** - Servers only start when needed
- **Minimal configs** - Only essential settings

### Improve Responsiveness

```lua
-- Adjust debounce timings in server configs
flags = {
  debounce_text_changes = 150,  -- Default: 150ms
}
```

### Memory Usage

```bash
# Monitor LSP memory usage
:lua for _, client in ipairs(vim.lsp.get_clients()) do print(client.name, client.id) end
```

## Migration from Mason

If migrating from Mason:

1. **Disable Mason plugins** in your config
2. **Install servers manually** using system package managers
3. **Update server paths** if they differ from Mason locations
4. **Remove Mason-specific configs** and use native patterns
5. **Test each server** individually

The native setup is more reliable and faster than Mason-managed servers.
