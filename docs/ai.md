# AI Integration Guide

This guide covers CodeCompanion (Claude) and Copilot integration for AI-assisted coding.

## Overview

This configuration provides two AI systems:

- **CodeCompanion** - Chat interface with Claude 3.5 Sonnet for code analysis and assistance
- **Copilot** - Inline code suggestions (optional, can be enabled/disabled)

## CodeCompanion Setup

### Prerequisites

```bash
# Set API key (required)
export ANTHROPIC_API_KEY="your-api-key-here"

# Add to shell profile for persistence
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
```

### Core Features

- **Chat Interface** - Vertical split chat with Claude
- **Memory System** - Persistent context across sessions
- **Repository Awareness** - Automatic project understanding
- **Tool Integration** - File editing, command execution, code search
- **Diff Views** - Visual code change previews

### Key Bindings

#### Primary Actions

- `<leader>a` - Toggle AI chat buffer
- `<C-a>` - AI action palette
- `<leader>cc` - Inline AI assistant
- `ga` (Visual) - Add selection to AI chat

#### Code Analysis

- `<leader>ce` - Explain code
- `<leader>cf` - Fix code issues  
- `<leader>co` - Optimize code
- `<leader>ct` - Generate tests
- `<leader>cd` - Explain diagnostics

#### Repository Context

- `<leader>cr` - Repository overview
- **Web search** - Built-in search capabilities
- **Code search** - Fast ripgrep integration

### Memory System

CodeCompanion uses multiple memory sources for context:

#### Personal Context (`CLAUDE.md`)

Create in project root or `~/.claude/CLAUDE.md`:

```markdown
# Personal AI Context

## Preferences
- Use TypeScript for new JavaScript projects
- Prefer functional programming patterns
- Always include error handling
- Use descriptive variable names

## Recent Work
- Working on Neovim configuration
- Focus on native LSP setup
- Debugging completion issues
```

#### Project Rules (`.cursorrules`)

Create in project root:

```markdown
# Project Rules

This is a Neovim configuration project.

## Conventions
- Use Lua for all configuration
- Follow lazy.nvim plugin patterns
- Prefer native Neovim features over plugins
- Document all custom functions

## Architecture
- Core settings in lua/core/
- Plugins in lua/plugins/
- LSP configs in lsp/ directory
```

### Chat Interface Usage

#### Starting a Chat

1. Press `<leader>a` to open chat buffer
2. Context automatically loaded from memory files
3. Ask questions or describe what you need
4. AI responses include actionable code changes

#### Repository Commands

Use slash commands for instant context:

```
/repo     - Complete repository overview
/tree     - Directory structure
/recent   - Recently modified files
```

Use @ tools for deeper analysis:

```
@repository_analyzer type=overview      - Project statistics
@repository_analyzer type=config        - Configuration analysis
@repository_analyzer type=dependencies  - Dependency analysis
@ripgrep_search pattern="function"      - Fast code search
```

#### Example Chat Session

```
User: /repo

AI: 📁 Repository Overview
Branch: main
Key files:
- init.lua (Neovim entry point)
- lua/core/options.lua (Core settings)
- lsp/init.lua (LSP coordination)
...

User: Explain the LSP setup in this repo

AI: This repository uses Neovim 0.11+ native LSP without Mason...
[Detailed explanation with code references]

User: @ripgrep_search pattern="vim.lsp.config"

AI: 🔍 Search results for 'vim.lsp.config':
lsp/init.lua:45: vim.lsp.config(server_name, config)
lua/plugins/native-lsp.lua:12: -- Uses vim.lsp.config() pattern
...
```

### Tool Integration

#### Available Tools

- **cmd_runner** - Execute shell commands with AI oversight
- **insert_edit_into_file** - Direct file modifications
- **ripgrep_search** - Fast text search across repository
- **repository_analyzer** - Deep repository analysis
- **web_search** - Internet search for documentation/solutions

#### Example Tool Usage

```
User: @cmd_runner command="npm test"

AI: I'll run the npm test command for you.
[Command execution and output analysis]

User: @insert_edit_into_file file="lua/core/options.lua" content="vim.opt.number = true"

AI: I'll add line numbers to your Neovim configuration.
[Shows diff preview and applies change]
```

## Copilot Integration

### Current Configuration

Copilot is configured but inline suggestions are **disabled by default** to avoid conflicts with native LSP completion.

### Enabling Copilot Suggestions

Edit `lua/plugins/copilot.lua`:

```lua
suggestion = {
  enabled = true,           -- Enable inline suggestions
  auto_trigger = true,      -- Auto-show suggestions
  keymap = {
    accept = '<Tab>',       -- Accept suggestion
    accept_word = '<C-Right>',  -- Accept next word
    accept_line = '<C-l>',  -- Accept line
    dismiss = '<C-e>',      -- Dismiss (stay in insert mode)
    next = '<C-]>',         -- Next suggestion
    prev = '<C-[>',         -- Previous suggestion
  },
},
```

### Copilot vs LSP Completion

| Feature | LSP Completion | Copilot |
|---------|----------------|---------|
| **Source** | Language servers | AI model |
| **Speed** | Instant | ~100-500ms |
| **Accuracy** | High for syntax | High for context |
| **Offline** | ✅ | ❌ |
| **Context** | Current file | Multi-file + web |

### Recommended Usage

1. **Keep LSP completion** for fast, accurate completions
2. **Enable Copilot** for complex logic and boilerplate
3. **Use CodeCompanion** for analysis and refactoring

## Troubleshooting

### CodeCompanion Issues

#### API Key Problems

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY

# Test API connection
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     https://api.anthropic.com/v1/messages
```

#### Chat Buffer Not Opening

```vim
:CodeCompanion log              " Check logs
:checkhealth codecompanion      " Health check
```

#### Memory Not Loading

```bash
# Check memory files exist and are readable
ls -la CLAUDE.md .cursorrules
cat CLAUDE.md
```

### Copilot Issues

#### Authentication

```vim
:Copilot auth                   " Authenticate with GitHub
:Copilot status                 " Check status
```

#### Suggestions Not Appearing

```lua
-- Check Copilot status
:lua print(require('copilot.client').is_disabled())

-- Restart Copilot
:Copilot disable
:Copilot enable
```

### Performance Issues

#### Slow Responses

- **Check internet connection** for AI services
- **Reduce memory file size** if too large
- **Limit repository context** for large projects

#### Memory Usage

```vim
:lua collectgarbage("collect")   " Force garbage collection
```

## Best Practices

### Effective Prompting

1. **Be specific** about what you want
2. **Provide context** about the project/file
3. **Ask for explanations** not just code
4. **Use tools** for repository analysis

### Memory Management

1. **Keep CLAUDE.md updated** with current preferences
2. **Update .cursorrules** for project-specific patterns
3. **Use descriptive commit messages** for git context
4. **Organize memory files** by topic/project

### Workflow Integration

1. **Start with CodeCompanion** for analysis and planning
2. **Use LSP completion** for fast, accurate coding
3. **Enable Copilot** for complex implementations
4. **Review AI suggestions** before accepting

## Advanced Configuration

### Custom Memory Sources

Add custom memory files in CodeCompanion config:

```lua
memory = {
  custom = {
    description = 'Team coding standards',
    parser = 'claude',
    files = {
      'TEAM_STANDARDS.md',
      'docs/style-guide.md',
    },
  },
}
```

### Custom Tools

Create project-specific tools:

```lua
tools = {
  test_runner = {
    callback = function(args)
      local test_file = args and args.file or 'all'
      return vim.fn.system('npm test ' .. test_file)
    end,
    description = 'Run project tests',
  },
}
```

### Integration with LSP

CodeCompanion automatically integrates with your LSP setup:

- **Error context** from diagnostics
- **Symbol information** from LSP servers
- **Project structure** from LSP workspace folders
- **File type detection** from LSP filetypes
