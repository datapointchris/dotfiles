-- Auto-generated highlights init
local M = {}

function M.setup(colors)
  local highlights = {}

  for _, mod in ipairs({ 'editor', 'syntax', 'treesitter', 'lsp', 'plugins' }) do
    local ok, hl_mod = pcall(require, 'charcoal_ember.highlights.' .. mod)
    if ok then
      for hl, spec in pairs(hl_mod.setup(colors)) do
        highlights[hl] = spec
      end
    end
  end

  return highlights
end

return M
