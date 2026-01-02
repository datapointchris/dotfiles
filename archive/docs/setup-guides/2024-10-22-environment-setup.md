# Environment Configuration Guide

## Overview

Each platform requires a `~/.env` file with specific environment variables that control dotfiles behavior and application features.

## Required Environment Variables

### Core Variables

```bash
export PLATFORM=macos           # Platform identifier (macos, wsl, ubuntu, arch)
export NVIM_AI_ENABLED=true     # Enable/disable AI features in Neovim
```

### Platform Examples

**macOS** (`~/.env`):

```bash
export PLATFORM=macos
export NVIM_AI_ENABLED=true
# Add API keys and other secrets here
# export ANTHROPIC_API_KEY="your-key-here"
```

**WSL** (`~/.env`):

```bash
export PLATFORM=wsl
export NVIM_AI_ENABLED=false
# Add API keys and other secrets here
```

## Validation

### ZSH Startup Validation

The ZSH configuration automatically validates the `.env` file on startup:

- ✔️ Confirms `.env` file exists
- ✔️ Validates required variables are set
- ❌ Shows errors if variables are missing

### Neovim Startup Validation

Neovim checks for required environment variables and shows conspicuous error notifications if they're missing.

## Usage in Configurations

### Neovim Plugins

```lua
-- Conditional plugin loading
cond = vim.env.NVIM_AI_ENABLED == "true"

-- Platform-specific logic
if vim.env.PLATFORM == "macos" then
  -- macOS specific config
elseif vim.env.PLATFORM == "wsl" then
  -- WSL specific config
end
```

### Shell Scripts

```bash
if [[ "$PLATFORM" == "macos" ]]; then
  # macOS specific behavior
fi

if [[ "$NVIM_AI_ENABLED" == "true" ]]; then
  # AI features enabled
fi
```

## Benefits

1. **Security** - API keys stay out of repository
2. **Flexibility** - Easy feature toggling per platform
3. **Validation** - Immediate feedback on startup
4. **Consistency** - Standardized environment pattern
5. **Extensibility** - Easy to add new variables

## Adding New Variables

1. Add to `.env` file on each platform
2. Update validation in `common/.config/zsh/.zshrc`
3. Update validation in `common/.config/nvim/init.lua`
4. Use in configurations as needed

## Error Handling

If environment variables are missing:

- ZSH will show ❌ errors during shell startup
- Neovim will show error notifications
- Features dependent on variables will be disabled
