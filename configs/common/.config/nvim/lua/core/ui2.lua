-- Native message + cmdline UI (Neovim 0.12 'ui2') — the in-core successor to
-- noice.nvim for the messages/cmdline presentation layer. It keeps the cmdline
-- and search at the bottom, highlights the cmdline as you type, drops the
-- hit-enter prompts, and shows long output in a pager buffer. Notifications are
-- handled separately by fidget (via vim.notify); ui2 only owns messages and the
-- cmdline.
--
-- ui2 lives under the private vim._core namespace and is experimental, so the
-- require is pcall-guarded: a future runtime that moves or renames it degrades
-- to Neovim's default message UI instead of erroring on startup.
local ok, ui2 = pcall(require, 'vim._core.ui2')
if not ok then
  vim.notify('ui2 unavailable; using default message UI', vim.log.levels.WARN, { title = 'UI' })
  return
end

-- Defaults route messages to the cmdline and spill overflow to the pager.
ui2.enable({ enable = true })
