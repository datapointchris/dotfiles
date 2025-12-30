-- Auto-generated colorscheme: Popping and Locking
local M = {}

M.config = {
  transparent = false,
  dim_inactive = false,
  terminal_colors = true,
}

function M.setup(opts)
  M.config = vim.tbl_deep_extend('force', M.config, opts or {})
end

function M.load()
  if vim.g.colors_name then
    vim.cmd('hi clear')
  end

  vim.g.colors_name = 'popping-and-locking'
  vim.o.termguicolors = true
  vim.o.background = 'dark'

  local colors = require('popping_and_locking.palette')
  local highlights = {}

  -- Collect all highlight groups
  for _, mod in ipairs({ 'editor', 'syntax', 'treesitter', 'lsp', 'plugins' }) do
    local ok, hl_mod = pcall(require, 'popping_and_locking.highlights.' .. mod)
    if ok then
      for hl, spec in pairs(hl_mod.setup(colors)) do
        highlights[hl] = spec
      end
    end
  end

  -- Apply highlights
  for hl, spec in pairs(highlights) do
    vim.api.nvim_set_hl(0, hl, spec)
  end

  -- Terminal colors
  if M.config.terminal_colors then
    local p = colors.palette
    vim.g.terminal_color_0 = p.base00
    vim.g.terminal_color_1 = p.base08
    vim.g.terminal_color_2 = p.base0B
    vim.g.terminal_color_3 = p.base0A
    vim.g.terminal_color_4 = p.base0D
    vim.g.terminal_color_5 = p.base0E
    vim.g.terminal_color_6 = p.base0C
    vim.g.terminal_color_7 = p.base05
    vim.g.terminal_color_8 = p.base03
    vim.g.terminal_color_9 = p.base08
    vim.g.terminal_color_10 = p.base0B
    vim.g.terminal_color_11 = p.base0A
    vim.g.terminal_color_12 = p.base0D
    vim.g.terminal_color_13 = p.base0E
    vim.g.terminal_color_14 = p.base0C
    vim.g.terminal_color_15 = p.base07
  end
end

return M
