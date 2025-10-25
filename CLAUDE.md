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
- `common/` - Common dotfiles between all operating systems
- `macos/` - MacOS specific dotfiles and configuration
- `wsl/` - WSL using Ubuntu specific dotfiles for use on a slightly restricted work computer
- `docs/` - documentation for the dotfiles, stored in mkdocs style
- Platform-specific Git configs with different editors/credentials

## Coding Preferences

- **Architecture**: DRY principles, intelligent symlink management
- **LSP**: Native Neovim LSP over plugin ecosystems when possible
- **AI Assistance**: Prefer comprehensive explanations with implementation
- **Documentation**: Clear README files, inline comments for complex logic
- **Testing**: Pre-commit hooks, shell validation, configuration testing

## Documentation Philosophy

When creating or updating documentation:

### Audience

- **Primary**: Future me (6+ months later) trying to remember why decisions were made
- **Secondary**: Technical developers familiar with the technology stack
- **Context**: Always within the broader dotfiles project ecosystem

### Content Focus

- **WHY over WHAT**: Architectural decisions, trade-offs
- **Context over Code**: How components fit together, not implementation details
- **Stability over Examples**: Principles that don't change vs code that does

### Documentation Structure

Avoid creating too many bulleted lists. A bulleted list loses a lot of information that long form sentences and explanations can maintain. Prefer to always talk in a person to person manner as if having a conversation with another developer on a pull request that was created to explain the code and how the project works.

**Documentation Guidelines:**

- Focus on **concise architectural explanations** rather than verbose step-by-step processes
- Emphasize **how systems work together** and **why they are designed that way**
- Use **paragraphs of explanation** as the primary structure for conveying context and reasoning
- Include **selective bulleted lists** for overviews only, not as the main documentation format
- Keep **code snippets minimal** - include command names or key concepts, not full implementations
- Maintain a **conversational tone** as if explaining technical decisions to another developer

Avoid documentation that is primarily bulleted lists or verbose procedural steps. Instead, focus on architectural understanding and the reasoning behind design decisions.

### Writing Style

- **Technical, not promotional**: State facts and reasoning, not "features"
- **Context-aware**: Reference other dotfiles components and decisions
- **Decision-focused**: Document the "why" behind choices made
- **Maintenance-oriented**: Help future maintenance and debugging

### Avoid

- ❌ Marketing language ("amazing", "powerful", "best")
- ❌ Step-by-step tutorials (they go stale)
- ❌ Extensive code examples (reference files instead)
- ❌ Feature lists without context or reasoning

## Recent Work

1. Completed migration from Mason LSP to native vim.lsp.config()
2. Implemented 20+ language servers (Python, JavaScript, Lua, etc.)
3. Enhanced CodeCompanion with memory system and VSCode-like experience
4. Integrated Claude 3.5 Sonnet adapter with project context awareness

## Communication Style

- Like to understand the "why" behind architectural decisions
- Prefer seeing the code changes implemented rather than just described
- Value cross-platform compatibility considerations

## Current Goals

- Optimize CodeCompanion workflow for seamless AI-assisted development
- Maintain clean, conflict-free native LSP configuration
- Document setup for future maintenance and sharing
- Create efficient development workflows across all platforms
