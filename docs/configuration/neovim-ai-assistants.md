# Neovim AI Assistants

Clean, focused AI assistance using existing paid services. Separate tools for separate purposes - keep Neovim simple while leveraging AI where it works best.

## Tools

| Tool | Provider | Purpose | Keybindings |
|------|----------|---------|-------------|
| **codecompanion.nvim** | GitHub Copilot | Chat, questions, explanations | `<leader>ca` (ask), `<leader>cc` (toggle), `<leader>cq` (quick actions) |
| **copilot.lua** | GitHub Copilot | Copilot backend for CodeCompanion | Suggestions disabled (uses blink-cmp integration) |
| **Claude Code** | Claude (via terminal) | Large refactors, multi-file changes | `Ctrl-g` (tmux popup), `<leader>tt` (floaterminal) |

## Workflow

**Quick questions:** `<leader>ca` → Ask Copilot → Get answer in chat window

**Large refactors:** `Ctrl-g` (tmux) or `<leader>tt` (neovim) → Claude Code CLI

## Why This Works

Each tool operates in its optimal environment - no integration complexity, no typing lag, uses existing subscriptions (GitHub Copilot, Claude). Copilot for quick tasks, Claude Code for focused work, Neovim stays fast and simple.

## Configuration

- `configs/common/.config/nvim/lua/plugins/codecompanion.lua` - Copilot chat
- `configs/common/.config/nvim/lua/plugins/copilot.lua` - Copilot backend
- `configs/common/.config/nvim/lua/core/keymaps.lua` - AI keybindings
