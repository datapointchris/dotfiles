-- Auto-generated highlights init
local M = {}

function M.setup(colors)
  local highlights = {}

  for _, mod in ipairs({ 'editor', 'syntax', 'treesitter', 'lsp', 'plugins' }) do
    local ok, hl_mod = pcall(require, 'tomorrow_night_bright.highlights.' .. mod)
    if ok then
      for hl, spec in pairs(hl_mod.setup(colors)) do
        highlights[hl] = spec
      end
    end
  end

  return highlights
end

return M
