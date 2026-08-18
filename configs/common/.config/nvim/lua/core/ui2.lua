-- Native message + cmdline UI (Neovim 0.12 'ui2'). It highlights the cmdline as
-- you type, drops the hit-enter prompts, and spills long output into a pager
-- buffer. fidget owns notifications via vim.notify; ui2 owns messages and the
-- cmdline, and plugins/tiny-cmdline.lua centres the cmdline window while a
-- command is being typed.
--
-- ui2 lives under the private vim._core namespace and is experimental — it was
-- vim._extui until 2026-02, and moved without a deprecation. The require is
-- pcall-guarded so the next move degrades to Neovim's default message UI
-- instead of erroring on startup.
local ok, ui2 = pcall(require, 'vim._core.ui2')
if not ok then
  vim.notify('ui2 unavailable; using default message UI', vim.log.levels.WARN, { title = 'UI' })
  return
end

-- Defaults route messages to the cmdline and spill overflow to the pager.
ui2.enable({ enable = true })
