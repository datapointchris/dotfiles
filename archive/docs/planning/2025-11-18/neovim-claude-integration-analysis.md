# Neovim Claude Integration - Comprehensive Analysis

**Date**: 2025-11-18
**Objective**: Find the best interactive Claude integration for small questions and file edits in Neovim, while keeping Claude Code CLI for larger changes.

---

## Executive Summary

**Current State**: You have a well-configured codecompanion.nvim setup that is currently **DISABLED** (`enabled = false` in config). Your claudecode.nvim is active and working for Claude Code CLI integration.

**Recommendation**: **Re-enable codecompanion.nvim** as your primary interactive plugin. It's already comprehensively configured with custom tools, slash commands, and Claude-specific optimizations. The configuration is production-ready and just needs to be activated.

**Rationale**: Starting with your existing, well-thought-out setup is lower risk than introducing a new plugin. Your codecompanion config shows deep customization (331 lines), indicating significant investment. If interactivity issues persist, we can troubleshoot or pivot to alternatives.

---

## Current Setup Analysis

### 1. claudecode.nvim (ACTIVE)

```lua
Location: platforms/common/.config/nvim/lua/plugins/claudecode.lua
Status: ✅ Enabled and configured
Keybindings: <leader>c* (cc, cf, cr, cm, cb, cs, aa, ad)
```

**Strengths:**

- Direct WebSocket integration with Claude Code CLI
- Maintains full Claude Code capabilities (tools, MCP, agents)
- Native diff accept/deny commands
- Works with your Claude Max plan via terminal

**Weaknesses:**

- Requires external terminal (splits your focus)
- Diff functionality has known issues (GitHub issue #136)
- Not truly "in-buffer" interactive experience
- Better suited for larger, multi-file changes

**Verdict**: Keep this for large refactors and complex multi-step tasks via Claude Code CLI.

---

### 2. codecompanion.nvim (DISABLED)

```lua
Location: platforms/common/.config/nvim/lua/plugins/codecompanion.lua
Status: ⚠️ Disabled (enabled = false, line 6)
Condition: NVIM_AI_ENABLED == 'true' ✅
Config Lines: 331 (highly customized)
```

**Your Configuration Highlights:**

- **Custom Tools**: `ripgrep_search`, `repository_analyzer`, `web_search`, `quick_search`
- **Slash Commands**: `/web`, `/repo` for quick context
- **Memory System**: CLAUDE.md, project context auto-loading
- **Diff Integration**: mini.diff configured (line 307-310)
- **Chat Layout**: Vertical right panel (35% width, 80% height)
- **Inline Assistant**: Configured with diff keymaps (gda, gdr, gdy)

**Why It's Disabled:**
Your keymaps.lua shows codecompanion keybindings are present but gated behind `companion_enabled == 'false'` (line 123-124), which overrides the `NVIM_AI_ENABLED` check.

**2025 Updates (from research):**

- Native inline diff improvements
- "Super Diff" for agent edit tracking
- Enhanced floating diff UI
- Better claude_code adapter support
- Community actively improving diff workflows

**Strengths:**

- **Conversational**: True back-and-forth chat (unlike avante.nvim)
- **In-Buffer Questions**: Chat opens as side panel, doesn't hijack terminal
- **File Context**: Auto-watch buffers, variables system for context injection
- **Multi-File Aware**: Repository analyzer tool, ripgrep integration
- **Diff View**: mini.diff integration with accept/reject keymaps
- **Extensible**: Your config shows deep customization potential
- **Well-Maintained**: Active development, responsive to community feedback

**Weaknesses (per your note):**

- You mentioned "interactivity doesn't work well" - need to investigate why
- Possible issues: adapter config, API key, or keybinding conflicts

**Verdict**: **This is your best starting point.** The config is excellent. Let's enable it and troubleshoot any issues.

---

## Alternative Options (If CodeCompanion Fails)

### 3. avante.nvim (Cursor-Like Experience)

```yaml
Repository: yetone/avante.nvim
Status: Not installed
Claude Support: ✅ claude-sonnet-4-20250514
```

**Strengths:**

- **Best Diff UX**: Cursor-like apply/reject workflow
- **Agentic Mode**: Can use tools for automatic code generation
- **Tool System**: bash, git_diff, git_commit, file operations, web_search
- **Project Context**: Auto-loads avante.md from project root
- **Active Community**: Highly discussed, well-maintained

**Weaknesses:**

- **Not Conversational**: Each message is standalone (no chat history)
- **Heavier**: More complex setup than codecompanion
- **Different Paradigm**: Designed for Cursor-style suggestions, not chat

**Use Case**: If you prioritize diff ergonomics over conversational flow.

**Migration Effort**: Medium (new plugin, new mental model)

---

### 4. folke/sidekick.nvim (Modern, NEW)

```yaml
Repository: folke/sidekick.nvim
Released: September 30, 2025 (3 months old)
Requires: Neovim >= 0.11.2
```

**Strengths:**

- **Rich Diffs**: Word/character-level granular diffing
- **Hunk Navigation**: Review edits one-by-one before applying
- **AI CLI Integration**: Built-in terminal for Claude, Gemini, Copilot CLI
- **Pre-configured**: Out-of-box Claude support
- **Modern Design**: Treesitter-based syntax highlighting in diffs

**Weaknesses:**

- **Very New**: Only 3 months old (stability unknown)
- **Neovim 0.11.2+**: Requires recent Neovim (check your version)
- **Less Documentation**: Newer means less community knowledge
- **Unknown Production Readiness**: Early adopter risk

**Use Case**: If you want the newest, most polished diff experience and are comfortable with bleeding edge.

**Migration Effort**: Medium-High (new plugin, requires Neovim upgrade if needed)

---

### 5. Other Options (Not Recommended)

**pasky/claude.vim**:

- Vim script (not Lua)
- Good diff mode, but less feature-rich
- Better alternatives exist

**IntoTheNull/claude.nvim**:

- Less active development
- Fewer features than codecompanion or avante

---

## Decision Matrix

| Feature | codecompanion.nvim | avante.nvim | sidekick.nvim | claudecode.nvim |
|---------|-------------------|-------------|---------------|-----------------|
| **Conversational Chat** | ✅ Excellent | ❌ Standalone messages | ✅ Good | ⚠️ Via terminal |
| **Diff View Quality** | ✅ Good (mini.diff) | ✅✅ Excellent | ✅✅ Excellent | ⚠️ Known issues |
| **In-Buffer Questions** | ✅ Side panel | ✅ Inline | ✅ Integrated | ❌ Terminal only |
| **Multi-File Context** | ✅ Custom tools | ✅ Agentic mode | ✅ CLI integration | ✅ Full Claude Code |
| **Claude Max Plan** | ✅ Direct API | ✅ Direct API | ✅ CLI/API | ✅ CLI (ACP) |
| **Configuration Effort** | ✅ Already done! | 🔶 Medium | 🔶 Medium | ✅ Already done! |
| **Stability** | ✅ Mature (2+ years) | ✅ Mature (1+ year) | ⚠️ New (3 months) | ✅ Mature |
| **Your Familiarity** | ✅ Already configured | ❌ New | ❌ New | ✅ Active use |
| **Maintenance Burden** | ✅ Low (keep config) | 🔶 Medium | 🔶 Unknown | ✅ Low |

---

## Recommended Action Plan

### Phase 1: Re-enable codecompanion.nvim (Lowest Risk)

**Why Start Here:**

1. You've already invested time in a 331-line configuration
2. It has all the features you need (chat, diff, context, tools)
3. Zero new plugin overhead
4. We can troubleshoot specific interactivity issues

**Steps:**

1. Change `enabled = false` to `enabled = true` in `codecompanion.lua` (line 6)
2. Change `companion_enabled = 'false'` to `companion_enabled = 'true'` in `keymaps.lua` (line 123)
3. Verify `ANTHROPIC_API_KEY` is set in your environment
4. Test basic workflows:
   - Open a file → `<leader>a` to toggle chat → Ask a question about the buffer
   - Select code → `ga` to add to chat → Request a change
   - Use inline assistant → `<leader>cc` → Request edit with diff
5. Document what "doesn't work well" specifically:
   - Is it slow?
   - Does diff not appear?
   - Are responses incorrect?
   - Keybindings not working?

**Expected Outcome:**

- If it works: You're done! Best setup with minimal change.
- If issues persist: Clear data on what to fix or switch.

---

### Phase 2: Troubleshoot or Pivot (If Needed)

**If codecompanion issues are fixable:**

- Check adapter configuration (lines 151-166)
- Verify mini.diff integration (lines 323-330)
- Test with simpler prompts
- Check for keybinding conflicts
- Review logs (`:CodeCompanionLogs`)

**If codecompanion issues are fundamental:**

- Proceed to Phase 3

---

### Phase 3: Switch to avante.nvim (If CodeCompanion Fails)

**Why avante.nvim as backup:**

- Best diff/apply workflow (your priority)
- Proven in production (many users)
- Still gets file context and tool usage
- Trade-off: Lose conversational history (acceptable for "small questions" use case)

**Configuration Approach:**

```lua
-- New file: platforms/common/.config/nvim/lua/plugins/avante.lua
return {
  'yetone/avante.nvim',
  build = 'make',
  dependencies = {
    'nvim-lua/plenary.nvim',
    'MunifTanjim/nui.nvim',
    'nvim-tree/nvim-web-devicons',
  },
  opts = {
    provider = 'claude',
    claude = {
      model = 'claude-sonnet-4-20250514',
      api_key_name = 'ANTHROPIC_API_KEY',
    },
    -- Keep file_selector = 'native' to use your existing telescope
    -- Integrate with your existing diffview.nvim
  },
}
```

**Disable codecompanion:**

- Set `enabled = false` again in codecompanion.lua
- Comment out keybindings in keymaps.lua

---

### Phase 4: Evaluate sidekick.nvim (Optional, Later)

**When to consider:**

- You're comfortable with bleeding edge
- You've upgraded to Neovim 0.11.2+
- You want the absolute best diff visualization
- You're willing to troubleshoot a new plugin

**Not Recommended Now Because:**

- Too new (3 months old)
- Adds risk when you have working alternatives
- Better to revisit in 6 months when community knowledge grows

---

## Architecture: Two-Plugin Strategy

### Recommended Split

**codecompanion.nvim (or avante.nvim)**: In-Neovim Interactivity

- Quick questions about current buffer
- Small edits with visual diff
- Code explanations
- LSP-aware refactoring
- Single-file or closely related files

**claudecode.nvim**: Claude Code CLI Bridge (Keep)

- Large multi-file refactors
- Project-wide changes
- Complex tool usage (bash, git, etc.)
- Tasks requiring extended agent workflows
- When you need full Claude Code capabilities

**Why This Works:**

- Clear separation of concerns
- Each tool does what it's best at
- No conflicts (different keybinding prefixes: `<leader>c` vs `<leader>a`)
- Maximum flexibility

---

## Risk Analysis

### Low Risk: Re-enable codecompanion.nvim

- Config already exists
- Known plugin (olimorris, trusted maintainer)
- Easy to disable again if issues persist
- **Recommendation: Start here**

### Medium Risk: Switch to avante.nvim

- New plugin to learn
- Configuration from scratch
- Different mental model
- But: Proven in production, active community
- **Recommendation: Fallback option**

### High Risk: Try sidekick.nvim

- Very new (3 months)
- Unknown stability
- Less community support
- May require Neovim upgrade
- **Recommendation: Revisit in 6 months**

---

## Testing Plan (After Re-enabling CodeCompanion)

### Test 1: Basic Chat

1. Open a Lua file in your dotfiles
2. Press `<leader>a` to toggle chat
3. Type: "Explain what this file does"
4. Verify: Chat opens, Claude responds, context is correct

### Test 2: Buffer Context

1. Open a file with a function
2. Press `<leader>ce` (explain)
3. Verify: Claude explains the current function without needing to paste code

### Test 3: Inline Edit with Diff

1. Select a block of code (visual mode)
2. Press `<leader>cc`
3. Type: "Add error handling to this code"
4. Verify: Diff appears with changes, you can accept with `gda` or reject with `gdr`

### Test 4: Multi-File Context

1. Open a file
2. Press `<leader>cr` (repository overview)
3. Ask: "Where is the X functionality implemented?"
4. Verify: Claude uses repository_analyzer tool and searches correctly

### Test 5: Custom Tools

1. In chat, type: `@quick_search pattern='TODO'`
2. Verify: Ripgrep results appear in chat
3. Ask a follow-up about the results
4. Verify: Conversational history is maintained

---

## Configuration Changes Required

### Step 1: Enable codecompanion.nvim

**File**: `platforms/common/.config/nvim/lua/plugins/codecompanion.lua`

**Change Line 6:**

```lua
-- FROM:
enabled = false,

-- TO:
enabled = true,
```

### Step 2: Enable codecompanion keybindings

**File**: `platforms/common/.config/nvim/lua/core/keymaps.lua`

**Change Line 123:**

```lua
-- FROM:
local companion_enabled = 'false'

-- TO:
local companion_enabled = 'true'
```

### Step 3: Verify Environment

**Run in terminal:**

```bash
# Check NVIM_AI_ENABLED is set
echo $NVIM_AI_ENABLED  # Should output: true

# Check ANTHROPIC_API_KEY is set
echo $ANTHROPIC_API_KEY  # Should output: sk-ant-...

# Check Neovim version (for future sidekick.nvim consideration)
nvim --version  # Note the version
```

### Step 4: Restart Neovim

```vim
:Lazy sync
:q
# Reopen Neovim
```

---

## Keybinding Reference (After Enabling)

### codecompanion.nvim (if enabled)

```html
<leader>ca  - AI Action Palette (quick access to all features)
<leader>a   - Toggle AI Chat (main interface)
ga          - Add visual selection to chat
<leader>cc  - Inline assistant (normal), Process selection (visual)
<leader>ce  - Explain code
<leader>cf  - Fix code
<leader>co  - Optimize code
<leader>ct  - Generate tests
<leader>cd  - Explain diagnostics
<leader>cw  - Web search (word/selection)
<leader>cs  - Quick code search
<leader>cr  - Repository overview
gda         - Accept diff change
gdr         - Reject diff change
gdy         - Accept all changes
```

### claudecode.nvim (keep for CLI work)

```html
<leader>cc  - Toggle Claude Code terminal
<leader>cf  - Focus Claude Code terminal
<leader>cr  - Resume Claude Code session
<leader>cC  - Continue Claude Code session
<leader>cm  - Select Claude model
<leader>cb  - Add current buffer to Claude Code
<leader>cs  - Send selection to Claude Code (visual)
<leader>aa  - Accept diff (Claude Code)
<leader>ad  - Deny diff (Claude Code)
```

**Note**: There's a keybinding conflict (`<leader>cc`) between the two plugins. This is fine because:

- codecompanion uses `<leader>cc` for inline assistant
- claudecode uses `<leader>cc` for toggle terminal
- You'll use codecompanion for inline work, claudecode for terminal work
- If conflict is annoying, change claudecode to `<leader>ct` (toggle)

---

## Success Criteria

**You'll know the setup is working when:**

1. ✅ You can open a file and ask Claude a question in a side buffer without touching the terminal
2. ✅ Claude can read your current buffer and other files in the project
3. ✅ When Claude suggests a change, you see a diff and can accept/reject it
4. ✅ You can have a back-and-forth conversation about code
5. ✅ Small tasks feel natural in Neovim, large tasks still work well in Claude Code CLI

**You'll know you need to switch plugins if:**

1. ❌ Chat doesn't open or is unresponsive
2. ❌ Diffs never appear or are broken
3. ❌ Claude doesn't have access to file context
4. ❌ Responses are consistently poor quality
5. ❌ Keybindings don't work despite troubleshooting

---

## Next Steps

**After you review this analysis:**

1. **Decision Point**: Do you want to start with re-enabling codecompanion.nvim (recommended), or jump straight to trying a new plugin?

2. **If re-enabling codecompanion**: I'll make the two-line config changes and guide you through testing.

3. **If switching to avante.nvim**: I'll disable codecompanion, install avante, and configure it for your workflow.

4. **If trying sidekick.nvim**: I'll check your Neovim version, install sidekick, and set up the modern diff workflow.

**My Recommendation**: Start with option 2 (re-enable codecompanion). It's the path of least resistance, and your config shows you've already thought through the setup carefully. If it doesn't work, we'll have clear data on why, and switching to avante will be straightforward.

---

## Questions to Consider

1. **What specifically "doesn't work well" with codecompanion?**
   - Performance?
   - UX/keybindings?
   - Diff functionality?
   - Response quality?

2. **How important is conversational history?**
   - Critical → codecompanion or sidekick.nvim
   - Nice to have → avante.nvim is fine

3. **How comfortable are you with bleeding edge tools?**
   - Very comfortable → Consider sidekick.nvim
   - Prefer stability → codecompanion or avante

4. **What's your Neovim version?**
   - If >= 0.11.2 → All options available
   - If < 0.11.2 → sidekick.nvim not possible yet

---

## Conclusion

**Primary Recommendation**: Re-enable your existing codecompanion.nvim setup (2-line change) and troubleshoot any issues. It's the lowest-risk path with the highest potential reward.

**Fallback Recommendation**: If codecompanion fundamentally doesn't meet your needs, switch to avante.nvim for superior diff ergonomics (acceptable trade-off on conversational history for "small questions" use case).

**Future Consideration**: Keep an eye on sidekick.nvim as it matures over the next 6 months.

**Keep**: claudecode.nvim for large-scale changes via Claude Code CLI.

**Result**: A two-plugin architecture that gives you the best of both worlds—quick, interactive in-buffer help for small tasks and full Claude Code power for large refactors.

---

**Ready to proceed?** Let me know which path you'd like to take, and I'll implement it with you.
