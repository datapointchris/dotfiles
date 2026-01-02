# Neovim Claude Integration - Setup Complete

**Date**: 2025-11-18

## What Changed

### 1. Simplified codecompanion.nvim Configuration

- **Old**: 331 lines with broken custom tools
- **New**: 75 lines, clean and working
- **Removed**: All custom tools (ripgrep_search, web_search, repository_analyzer, slash commands)
- **Why**: Claude Sonnet 4.5 has these built-in. No need to reinvent the wheel.

### 2. Fixed Keybinding Conflicts

- **codecompanion**: `<leader>a` (chat), `<leader>cc` (inline edit)
- **claudecode**: `<leader>ct` (terminal), `<leader>cb` (add buffer)
- **No overlap**: Clear separation, most common actions only

### 3. Updated keymaps.lua

- Removed 45+ lines of broken codecompanion keybindings
- Added simple 4-line setup
- Enabled codecompanion properly

---

## Your Two-Plugin System

### codecompanion.nvim - Quick Interactive Help

**Purpose:** Chat with Claude in a side buffer for quick questions and small edits.

**When to use:**

- "What does this function do?"
- "Explain this code"
- "Add error handling to this block"
- Quick conversational help
- Single-file focused work

**How it works:**

1. `<leader>a` - Opens chat buffer on right side
2. Ask questions, get responses
3. Select code → `<leader>cc` → Request changes
4. Diff appears inline
5. `gda` to accept, `gdr` to reject

**Key feature:** Stays in Neovim, no terminal needed. Fast and conversational.

---

### claudecode.nvim - Claude Code CLI Inside Neovim

**Purpose:** Run the actual Claude Code CLI inside Neovim, with diffs appearing in your buffers.

**Important:** This IS Claude Code CLI, not a wrapper. You can use ALL Claude Code features:

- Say "look at the whole project" - works
- Say "analyze platforms/ directory" - works
- Use ALL tools, MCP, agentic features
- Full context awareness

**When to use:**

- Large multi-file refactors
- Complex changes requiring bash/git commands
- Agentic workflows (Claude plans and executes)
- When you need Claude Code's full power but want diffs in Neovim

**How it works:**

1. `<leader>ct` - Opens Claude Code CLI terminal inside Neovim (right split)
2. Use it **exactly like normal Claude Code CLI**:
   - "Look at the entire platforms directory"
   - "Analyze this project structure"
   - "Implement feature X across these files"
3. Claude Code works (full context, all tools)
4. **Diffs appear in your Neovim buffer automatically** (not in terminal)
5. `<leader>aa` to accept, `<leader>ad` to deny
6. Never leave Neovim

**Optional shortcuts:**

- `<leader>cb` - Quick "add current buffer" (convenience, not required)
- `<leader>cs` - Send selection (convenience, not required)

**Key feature:** Full Claude Code CLI with diffs in your editor instead of copy/paste.

---

## The Key Difference: claudecode vs Tmux Split

### Without claudecode.nvim (tmux split)

```text
┌─────────────────────────────────────────┐
│  Tmux                                   │
│  ┌────────────┬────────────────────┐   │
│  │  Neovim    │  Terminal          │   │
│  │            │  $ claude          │   │
│  │  [edit]    │  > Add file        │   │
│  │            │  > "refactor"      │   │
│  │            │  [copy code]       │   │
│  │  [paste]   │                    │   │
│  └────────────┴────────────────────┘   │
└─────────────────────────────────────────┘
```

**Problems:**

- Manual pane switching
- Manual copy/paste
- No visual diffs
- Claude doesn't know your context

### With claudecode.nvim

```text
┌─────────────────────────────────────────┐
│  Neovim (single window)                 │
│  ┌──────────────┬──────────────────┐   │
│  │  Buffer      │  Claude Terminal │   │
│  │              │  (embedded)      │   │
│  │  [DIFF HERE] │  > "refactor"    │   │
│  │  + new       │                  │   │
│  │  - old       │  Auto-context    │   │
│  │              │                  │   │
│  │  [Accept?]   │                  │   │
│  └──────────────┴──────────────────┘   │
└─────────────────────────────────────────┘
```

**Benefits:**

- Stay in Neovim
- Diffs appear automatically in buffer
- One keystroke to accept/deny
- Claude knows your current file
- Bidirectional communication

**The insight:** claudecode.nvim runs the **actual Claude Code CLI** inside Neovim. You get all Claude Code features (full project context, tools, MCP), but diffs appear in your Neovim buffers instead of requiring copy/paste. With tmux, diffs are just text in the terminal that you manually apply.

---

## Complete Keybinding Reference

### codecompanion.nvim (Quick Chat & Edits)

```html
<leader>a   - Toggle chat buffer (main usage)
<leader>cc  - Inline assistant (for edits with diff)
gda         - Accept diff
gdr         - Reject diff
```

Inside chat buffer:

```text
<C-s>       - Send message (normal or insert mode)
<C-c>       - Close chat
```

### claudecode.nvim (Claude Code CLI in Neovim)

```html
<leader>ct  - Open Claude Code CLI terminal (then use normally)
<leader>aa  - Accept diff (when Claude suggests changes)
<leader>ad  - Deny diff

Optional conveniences:
<leader>cb  - Quick "add current buffer" (not required)
<leader>cs  - Send selection (visual mode, not required)
```

**Note:** Once you open the terminal with `<leader>ct`, use Claude Code CLI exactly as you normally would. Say "look at platforms/", "analyze the project", etc. You have full context.

---

## Important Clarification: claudecode.nvim

### You Do NOT Need to Manually Add Files

**Common misconception:** "I need to use `<leader>cb` to add every file before Claude Code can see it."

**Reality:** No! claudecode.nvim runs the **actual Claude Code CLI**. You can:

- Say "look at the entire platforms/ directory" ✅
- Say "analyze all the symlinks code" ✅
- Say "show me every file that imports X" ✅
- Use ALL Claude Code features exactly as normal ✅

### What `<leader>cb` Actually Does

It's just a shortcut for: "add the file I'm currently editing to the conversation"

**You can skip it and just talk to Claude Code:**

```html
<leader>ct (opens terminal)
> "Analyze the entire dotfiles repository structure"
```

Claude Code handles context. Just like using it normally.

### The ONLY Benefit of claudecode.nvim

**Diffs appear in your Neovim buffers.**

That's it. That's the only reason to use it over tmux:

- With tmux: Diffs are text in terminal, you copy/paste
- With claudecode.nvim: Diffs appear in your editor, `<leader>aa` to accept

Everything else is **exactly the same** as Claude Code CLI.

---

## Testing Your Setup

### Step 1: Run Automated Tests (30 seconds)

```bash
cd ~/dotfiles
nvim --headless -c "luafile .planning/test-codecompanion-ephemeral.lua" -c "qa"
```

This checks:

- Environment variables set
- Plugin loads
- Commands registered
- Adapters configured
- Dependencies available

### Step 2: Manual Testing (2 minutes)

Open Neovim and test codecompanion:

1. **Chat test:**
   - Open any Lua file
   - Press `<leader>a`
   - Chat buffer opens on right? ✅/❌
   - Type: "what is this file?"
   - Claude responds? ✅/❌

2. **Inline edit test:**
   - Select a function (visual mode)
   - Press `<leader>cc`
   - Type: "add comments"
   - Diff appears? ✅/❌
   - Press `gda`
   - Changes applied? ✅/❌

Test claudecode (if you use Claude Code CLI):

3. **Bridge test:**
   - Open a file
   - Press `<leader>cb` (adds to Claude context)
   - Press `<leader>ct` (opens terminal in Neovim)
   - Terminal opens on right? ✅/❌
   - Type a request (e.g., "explain this file")
   - Claude responds in terminal? ✅/❌
   - If Claude suggests changes, diff appears in buffer? ✅/❌

### Step 3: Delete Test Script

```bash
rm .planning/test-codecompanion-ephemeral.lua
```

---

## Troubleshooting

### Chat doesn't open

- Check: `:echo $NVIM_AI_ENABLED` → Should be "true"
- Check: `:echo $ANTHROPIC_API_KEY` → Should be "sk-ant-..."
- Try: `:Lazy sync` to update plugins
- Check: `:CodeCompanionLogs` for errors

### Diff doesn't appear

- Verify mini.diff is installed: `:lua require('mini.diff')`
- Check codecompanion config: `:lua print(vim.inspect(require('codecompanion').config.display.diff))`
- Should see: `enabled = true, provider = 'mini_diff'`

### Claude gives weird responses

- You're using Claude Sonnet 4.5 via Anthropic API
- No need for custom tools—just ask naturally:
  - "Search the web for X" (Claude has web_search built-in)
  - "Find where Y is defined in this codebase" (Claude can read files)
  - "Explain this function" (Claude sees buffer context)

### Keybindings don't work

- Check: `:map <leader>a` → Should show CodeCompanionChat Toggle
- Check: `:map <leader>cc` → Should show CodeCompanion (for codecompanion) OR ClaudeCode (for claudecode)
- If conflicts exist, check for duplicate definitions in other plugin configs

---

## Real-World Usage Examples

### Example 1: Quick Question (codecompanion)

```bash
You're reading unfamiliar code.

1. Cursor on function
2. <leader>a (opens chat)
3. "What does this function do?"
4. Claude explains
5. Follow-up: "How is it called?"
6. Claude shows call sites
7. <C-c> when done
```

**Time:** 30 seconds
**Plugin:** codecompanion

---

### Example 2: Small Refactor (codecompanion)

```bash
You want to improve error handling in one function.

1. Select function (visual mode)
2. <leader>cc (inline assistant)
3. "Add error handling with early returns"
4. Diff appears
5. Review changes
6. gda (accept)
7. Done
```

**Time:** 1 minute
**Plugin:** codecompanion

---

### Example 3: Large Feature (claudecode)

```bash
You need to add authentication across controllers, routes, and tests.

1. <leader>ct (opens Claude Code CLI terminal in Neovim)
2. "Analyze the entire platforms/ directory and implement JWT
    authentication middleware across all API routes"
3. Claude Code does full analysis (reads all files, full project context)
4. Claude plans the changes
5. Asks for confirmation
6. You approve
7. Claude works (reads files, makes changes, runs tests)
8. Diffs appear in your Neovim buffers as Claude works
9. <leader>aa to accept each (or deny with <leader>ad)
10. Stay in Neovim the whole time

No manual file adding needed - just talk to Claude Code naturally!
```

**Time:** 5-10 minutes
**Plugin:** claudecode

---

## What You Removed (and Why It's Fine)

### Custom Tools (removed)

- `ripgrep_search` - Claude has file reading built-in
- `repository_analyzer` - Claude can analyze repos natively
- `web_search` - Claude Sonnet 4.5 has web_search tool
- `quick_search` - Redundant with Claude's capabilities

### Custom Slash Commands (removed)

- `/web` - Just ask "search the web for X"
- `/repo` - Just ask "analyze this repository"

### Memory System (simplified)

- Removed complex CLAUDE.md loading
- Claude maintains context within conversation
- Can manually add files to chat if needed

**Result:** Simpler, more reliable, uses Claude's actual capabilities instead of broken wrappers.

---

## Files Changed

```yaml
Modified:
- platforms/common/.config/nvim/lua/plugins/codecompanion.lua (75 lines, was 331)
- platforms/common/.config/nvim/lua/plugins/claudecode.lua (simplified keybindings)
- platforms/common/.config/nvim/lua/core/keymaps.lua (removed 45+ broken lines)

Backed up:
- platforms/common/.config/nvim/lua/plugins/codecompanion-old.lua.backup

Created (ephemeral):
- .planning/test-codecompanion-ephemeral.lua (delete after testing)
- .planning/neovim-claude-setup-complete.md (this file)
```

---

## Next Steps

1. **Run tests** (see Testing Your Setup above)
2. **Try it out** with real work
3. **Delete test script** when satisfied
4. **Archive planning docs** when done:

   ```bash
   mv .planning/neovim-claude-* .planning/archive/
   ```

---

## Configuration Reference

### codecompanion.lua (simplified)

```lua
-- 75 lines total
-- Strategies: chat (with keymaps), inline (with diff keymaps)
-- Display: vertical right panel, 35% width, 80% height
-- Diff: enabled with mini.diff provider
-- Log level: ERROR (quiet)
```

### claudecode.lua (simplified)

```lua
-- 6 keybindings (most common only)
-- Terminal: right split, 30% width
-- Diff: vertical split, auto-close on accept
-- Auto-start: true (WebSocket server for Claude Code CLI)
```

### keymaps.lua (simplified)

```lua
-- 2 keybindings for codecompanion
-- 6 keybindings for claudecode (defined in plugin file)
-- Gated by NVIM_AI_ENABLED == 'true'
```

---

## Philosophy

**Less is more:**

- No custom tools that don't work
- No nested config hell
- No features you don't need
- Just: chat, inline edits, diffs, accept/reject
- Let Claude's built-in capabilities do the work

**Clear separation:**

- codecompanion: Quick, conversational, single-file
- claudecode: Large, agentic, multi-file, full CLI power

**Simple keybindings:**

- Most common actions only
- No overlap
- Easy to remember

**Result:** A setup you understand and can maintain.

---

## Questions?

If something doesn't work:

1. Check `:CodeCompanionLogs`
2. Verify environment: `:echo $NVIM_AI_ENABLED` and `:echo $ANTHROPIC_API_KEY`
3. Try `:Lazy sync`
4. Check for plugin conflicts

If you want to customize:

- codecompanion.lua: Change window size, keybindings, adapter settings
- claudecode.lua: Change terminal position, diff behavior
- Everything is in one place, easy to modify

---

**You're all set!** Try it out and see how it feels.
