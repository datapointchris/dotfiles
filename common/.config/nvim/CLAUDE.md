# Claude AI Assistant - Neovim Development Context

## About Me

I'm Chris, a software engineer who uses a dotfiles-based development environment across macOS, WSL, and Ubuntu. I prefer clean, maintainable code and enjoy optimizing developer experience.

## Development Environment

- **Editor**: Neovim 0.11+ with native LSP configuration
- **Shell**: Zsh with custom prompt and enhanced CLI tools
- **Platforms**: macOS (primary), WSL, Ubuntu
- **Terminal**: iTerm2 on macOS, various on Linux
- **AI Coding**: CodeCompanion.nvim with Claude 3.5 Sonnet

## Current Project Context

Working on a cross-platform dotfiles repository with shared configurations and platform-specific overrides. Recently migrated from Mason-based LSP to Neovim 0.11 native LSP and enhanced CodeCompanion setup.

### Key Files

- `symlinks` - Core symlink management tool
- `shared/.config/zsh/` - Cross-platform shell configuration
- `macos/.config/nvim/` - Native LSP configuration
- Platform-specific Git configs with different editors/credentials

## Coding Preferences

- **Architecture**: DRY principles, intelligent symlink management
- **LSP**: Native Neovim LSP over plugin ecosystems when possible
- **AI Assistance**: Prefer comprehensive explanations with implementation
- **Documentation**: Clear README files, inline comments for complex logic
- **Testing**: Pre-commit hooks, shell validation, configuration testing

## Recent Work

1. Completed migration from Mason LSP to native vim.lsp.config()
2. Implemented 20+ language servers (Python, JavaScript, Lua, etc.)
3. Enhanced CodeCompanion with memory system and VSCode-like experience
4. Integrated Claude 3.5 Sonnet adapter with project context awareness

## Communication Style

- I appreciate step-by-step explanations for complex changes
- Like to understand the "why" behind architectural decisions
- Prefer seeing the code changes implemented rather than just described
- Value cross-platform compatibility considerations

## Current Goals

- Optimize CodeCompanion workflow for seamless AI-assisted development
- Maintain clean, conflict-free native LSP configuration
- Document setup for future maintenance and sharing
- Create efficient development workflows across all platforms
