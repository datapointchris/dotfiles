# Neovim Configuration Documentation

Technical documentation for the Neovim configuration implementing native LSP, custom colorscheme management, and unified formatting.

## Implementation Overview

This configuration addresses three primary development environment requirements:

1. **Corporate environment compatibility**: No external package managers or plugin dependencies that may be blocked
2. **Cross-platform consistency**: Identical behavior across macOS, WSL, and Linux
3. **Maintenance simplicity**: Preference for native Neovim features over complex plugin abstractions

## Architecture Decisions

### Native LSP Over Plugin Abstractions

**Problem**: Mason and nvim-lspconfig add abstraction layers that can break in corporate environments.

**Solution**: Direct `vim.lsp.enable()` calls with system-installed language servers.

**Trade-offs**: Manual server installation required, but eliminates dependency on external package managers.

### Custom Colorscheme Persistence

**Problem**: No existing plugin provided git-repository-aware colorscheme persistence.

**Solution**: Custom plugin using git working directory detection for per-project theme management.

**Trade-offs**: Additional maintenance burden, but provides exact required functionality without feature bloat.

### External Formatter Priority System

**Problem**: Inconsistent formatting between manual formatting, auto-save, and pre-commit hooks.

**Solution**: Unified formatter module prioritizing external tools (stylua, ruff, prettier) with LSP fallback.

**Trade-offs**: Dependency on system-installed formatters, but ensures consistency across all formatting contexts.

### Unified Completion Architecture

**Problem**: Multiple completion systems (native LSP, nvim-cmp, Copilot) competing for the same triggers.

**Solution**: Single nvim-cmp coordinator with all completion sources integrated as providers.

The completion system establishes a clear hierarchy where nvim-cmp manages all completions in a unified popup. LSP servers provide language-specific completions through the `nvim_lsp` source, while Copilot suggestions integrate via `copilot-cmp` rather than standalone overlays. This eliminates conflicts between Tab key handlers and ensures consistent behavior.

Escape key handling provides an intuitive workflow: pressing `<Esc>` when completions are visible dismisses the popup without exiting insert mode, allowing continued typing. A second `<Esc>` performs the standard mode transition. Manual completion triggers via `<C-;>` ensure completion is available even when auto-trigger is disabled for specific contexts.

**Critical Implementation Detail**: The Tab key logic differentiates between completion types to prevent "gibberish" insertions. When accepting a completion, the system checks if the selected item is a LuaSnip snippet (from `friendly-snippets`) and calls `luasnip.expand()` only for those. All other completions—LSP keywords, function names, Copilot suggestions—use `cmp.confirm()` which properly handles LSP snippet expansion through the language server protocol. This distinction is essential because LSP servers return snippet text with `$1`, `$2` placeholders that require different processing than LuaSnip's internal snippet format.

The source priority order matters for debugging: `lazydev` (group 0) takes precedence for Lua development, followed by `nvim_lsp`, `copilot`, `luasnip`, `buffer`, and `path` (all group 2). If completions aren't appearing from a specific source, check that the corresponding LSP server is attached and the source plugin is properly loaded.

**Trade-offs**: Requires disabling Neovim 0.11's built-in completion and managing nvim-cmp dependencies, but provides unified behavior across all completion sources.

## Component Documentation

| Component | Purpose | Implementation Details |
|-----------|---------|----------------------|
| [colorscheme-manager.md](./colorscheme-manager.md) | Git-based project colorscheme persistence | Custom plugin with telescope integration |
| [formatter.md](./formatter.md) | Unified formatting system | External formatter priority with LSP fallback |
| [lsp.md](./lsp.md) | Language server configuration | Native LSP setup for 20+ languages |
| [plugins.md](./plugins.md) | Plugin organization | Modular lazy-loading architecture |
| [core.md](./core.md) | Base configuration | Keymaps, options, autocmds |

## Configuration Structure

```text
common/.config/nvim/
├── init.lua                    # LSP server initialization
├── lua/
│   ├── core/                   # Base Neovim configuration
│   │   ├── options.lua         # Editor settings
│   │   ├── keymaps.lua         # Key bindings
│   │   ├── autocmds.lua        # Event handlers
│   │   └── lazy.lua            # Plugin manager setup
│   ├── plugins/                # Plugin configurations
│   │   ├── colorscheme-manager.lua  # Git-aware theme system
│   │   ├── telescope.lua       # File/symbol search
│   │   ├── treesitter.lua      # Syntax parsing
│   │   └── [other plugins]
│   └── utils/                  # Custom utilities
│       └── formatter.lua       # External formatter integration
└── lsp/                        # Language server configs
    ├── basedpyright.lua        # Python
    ├── lua_ls.lua              # Lua
    ├── rust_analyzer.lua       # Rust
    └── [other servers]
```

## Environment Conditionals

Platform and feature detection controls plugin loading:

```lua
-- AI tooling conditional loading
cond = vim.env.AI_ENABLED == "true"

-- Platform-specific behavior
if vim.env.PLATFORM == "macos" then
  -- macOS clipboard integration
elseif vim.env.PLATFORM == "wsl" then  
  -- WSL Windows clipboard bridge
end
```

## Installation Requirements

### System Dependencies

**LSP Servers**: Install via system package managers rather than Mason:

```bash
# Python
pip install basedpyright ruff

# JavaScript/TypeScript  
npm install -g typescript-language-server

# Rust
rustup component add rust-analyzer

# Go
go install golang.org/x/tools/gopls@latest
```

**External Formatters**: Required for unified formatting system:

```bash
# Core formatters
brew install stylua prettier  # macOS
npm install -g prettier       # Cross-platform
pip install ruff              # Python formatting
```

### Why System Installation Over Mason

**Corporate network restrictions**: Mason downloads from GitHub releases, often blocked.

**Version consistency**: System package managers provide stable, auditable tool versions.

**Explicit dependencies**: Clear requirements rather than hidden plugin management.

## Common Issues

| Problem | Root Cause | Solution |
|---------|------------|----------|
| LSP server not starting | Missing system installation | Install via package manager, not Mason |
| Colorscheme not persisting | Outside git repository | Initialize git repo or use manual theme selection |
| Formatting inconsistency | External formatter missing | Install system formatters matching pre-commit config |
| AI plugins not loading | Missing environment variable | Set `AI_ENABLED=true` in shell profile |

## Modification Guidelines

**Documentation updates**: Changes to functionality require corresponding documentation updates.

**Cross-platform testing**: Verify modifications work on both macOS and WSL.

**Dependency constraints**: New dependencies must be available via system package managers.

**Performance consideration**: Profile changes that affect startup time or editing responsiveness.

**Corporate compatibility**: Ensure changes work in environments with restricted network access.
