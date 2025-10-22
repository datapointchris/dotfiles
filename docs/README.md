# Neovim Configuration Documentation

This directory contains developer-focused documentation for understanding, setting up, and troubleshooting this Neovim configuration.

## Quick Start

1. **Setup**: See [Setup Guide](./setup.md) for installation and initial configuration
2. **LSP**: See [LSP Guide](./lsp.md) for language server setup and troubleshooting  
3. **AI Integration**: See [AI Guide](./ai.md) for CodeCompanion and Copilot configuration
4. **Troubleshooting**: See [Troubleshooting](./troubleshooting.md) for common issues

## Configuration Architecture

This configuration uses:

- **Native Neovim 0.11+ LSP** (no Mason, no nvim-lspconfig)
- **Native completion** with `vim.lsp.completion.enable()`
- **Modular plugin structure** in `lua/plugins/`
- **Custom LSP configurations** in `/lsp/` directory
- **AI integration** with CodeCompanion (Claude) and optional Copilot

## Directory Structure

```text
├── docs/                    # This documentation
├── docs/                    # This documentation
├── lsp/                     # Native LSP server configurations
│   ├── init.lua            # LSP setup and coordination
│   └── *.lua               # Individual server configs
├── lua/
│   ├── core/               # Core Neovim settings
│   └── plugins/            # Lazy.nvim plugin specifications
└── init.lua                # Entry point
```

## Key Features

- **20 Language Servers** configured for native LSP
- **AI Assistant** with Claude integration via CodeCompanion
- **Smart Completion** using native LSP + optional Copilot
- **Cross-platform** dotfiles with shared/platform-specific configs
- **Git Integration** with advanced workflow tools
- **Modern UI** with proper themes and statusline

## Documentation Index

- [Setup Guide](./setup.md) - Initial installation and configuration
- [LSP Configuration](./lsp.md) - Language server setup and native LSP
- [AI Integration](./ai.md) - CodeCompanion and Copilot setup
- [Corporate Environment](./corporate.md) - Solutions for restricted networks
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
- [Examples](./examples/) - MkDocs examples and reference material
