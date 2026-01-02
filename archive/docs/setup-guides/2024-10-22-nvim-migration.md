# Neovim Migration to Common Configuration

## Summary

Successfully consolidated nvim configuration using macOS as the base, with environment-based conditional loading for AI plugins.

## Changes Made

### 1. Base Configuration

- ✅ Copied macOS nvim config to `common/.config/nvim/`
- ✅ Removed `.DS_Store` files from common config
- ✅ macOS config is now the base for all platforms

### 2. Conditional AI Plugin Loading

Updated plugins with environment-based conditions:

**CodeCompanion** (`common/.config/nvim/lua/plugins/codecompanion.lua`):

```lua
cond = vim.env.MACOS == "true" or vim.env.AI_ENABLED == "true",
```

**Copilot** (`common/.config/nvim/lua/plugins/copilot.lua`):

```lua
cond = (vim.env.MACOS == "true" or vim.env.AI_ENABLED == "true") and not vim.g.vscode,
```

### 3. Environment Files Created

**macOS** (`macos/.env`):

```bash
export MACOS=true
export AI_ENABLED=true
export PLATFORM=macos
export DOTFILES_PLATFORM=macos
```

**WSL** (`wsl/.env`):

```bash
export WSL=true  
export AI_ENABLED=false
export PLATFORM=wsl
export DOTFILES_PLATFORM=wsl
```

## Key Differences Addressed

### ✅ Resolved

- **AI Plugins**: CodeCompanion & Copilot only load on macOS (AI_ENABLED=true)
- **Python venv selector**: Will be automatically excluded (not in common config)
- **LSP Structure**: Using updated macOS LSP structure as base
- **Lock file drift**: Common config will have single source of truth

### 🔄 To Be Handled

- **Platform-specific keymaps**: Need to review WSL-specific keybindings
- **File organization**: WSL had some plugins in different locations

## Next Steps

1. **Test the common configuration** - Link it and verify it works
2. **Update platform directories** - Remove nvim configs from macos/ and wsl/
3. **Handle any platform-specific differences** - Add overrides if needed
4. **Update symlinks** - Link common config to both platforms

## Environment Variable Usage

Plugins can now use these patterns:

```lua
-- macOS only
cond = vim.env.MACOS == "true"

-- WSL only  
cond = vim.env.WSL == "true"

-- AI features
cond = vim.env.AI_ENABLED == "true"

-- Platform-specific logic
if vim.env.PLATFORM == "macos" then
  -- macOS specific config
elseif vim.env.PLATFORM == "wsl" then
  -- WSL specific config
end
```

## Benefits

1. **Single source of truth** - All nvim config in `common/`
2. **No duplication** - Shared configurations exist once
3. **Clear AI boundaries** - AI plugins only on macOS  
4. **Easy maintenance** - Update once, applies everywhere
5. **Platform flexibility** - Easy to add new platforms
6. **Environment control** - Simple on/off switches for features
