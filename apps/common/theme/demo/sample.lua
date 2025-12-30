-- Sample Lua file for theme preview
local M = {}

-- Constants
local MAX_COLORS = 16
local DEFAULT_BG = '#1d2021'

-- Configuration table
M.config = {
  transparent = false,
  dim_inactive = true,
  terminal_colors = true,
}

-- Color palette
M.palette = {
  base00 = '#1d2021',
  base01 = '#3c3836',
  base08 = '#fb4934',
  base0B = '#b8bb26',
  base0D = '#83a598',
}

--- Setup function with options
---@param opts table? Optional configuration
function M.setup(opts)
  M.config = vim.tbl_deep_extend('force', M.config, opts or {})
end

--- Load the colorscheme
function M.load()
  -- Clear existing highlights
  if vim.g.colors_name then
    vim.cmd('hi clear')
  end

  vim.g.colors_name = 'gruvbox'
  vim.o.termguicolors = true

  -- Apply highlights
  local highlights = {
    Normal = { fg = M.palette.base05, bg = M.palette.base00 },
    Comment = { fg = M.palette.base03, italic = true },
    String = { fg = M.palette.base0B },
    Function = { fg = M.palette.base0D, bold = true },
  }

  for group, settings in pairs(highlights) do
    vim.api.nvim_set_hl(0, group, settings)
  end

  -- Numbers and booleans
  local count = 42
  local enabled = true
  local ratio = 3.14

  -- Conditional logic
  if M.config.transparent then
    highlights.Normal.bg = 'NONE'
  elseif M.config.dim_inactive then
    vim.notify('Dim inactive enabled', vim.log.levels.INFO)
  end

  -- Loop example
  for i = 1, MAX_COLORS do
    local color = string.format('color%d', i - 1)
    vim.g['terminal_' .. color] = M.palette['base0' .. string.format('%X', i)]
  end

  return true
end

return M
